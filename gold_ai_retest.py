"""Replay Gold AI candidate rules on a Dukascopy XAUUSD M1 BID CSV.

Usage: python3 gold_ai_retest.py candles.csv --cost 0.50 --cost 1.00
Costs are assumed round-trip USD per unit. Results and trade logs go to stdout.
"""

import argparse
import csv
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math


@dataclass(frozen=True)
class Bar:
    minute: int
    open: float
    high: float
    low: float
    close: float


def read_bars(path):
    bars = []
    with open(path, newline="", encoding="utf-8-sig") as source:
        for row in csv.DictReader(source):
            stamp = datetime.fromisoformat(row["Etc/UTC"])
            if stamp.utcoffset() != timezone.utc.utcoffset(stamp) or stamp.timestamp() % 60:
                raise ValueError("Expected UTC minute boundaries")
            bar = Bar(int(stamp.timestamp() // 60), *(float(row[k]) for k in ("Open", "High", "Low", "Close")))
            if not (all(math.isfinite(x) and x > 0 for x in (bar.open, bar.high, bar.low, bar.close))
                    and bar.low <= min(bar.open, bar.close) <= max(bar.open, bar.close) <= bar.high):
                raise ValueError(f"Invalid OHLC at {stamp}")
            if bars and bar.minute <= bars[-1].minute:
                raise ValueError("Expected unique ascending timestamps")
            bars.append(bar)
    if not bars:
        raise ValueError("CSV has no candles")
    return bars


def complete_buckets(bars, size):
    groups = {}
    for bar in bars:
        groups.setdefault(bar.minute // size * size, []).append(bar)
    return {
        start + size: Bar(start, group[0].open, max(b.high for b in group),
                          min(b.low for b in group), group[-1].close)
        for start, group in groups.items() if len(group) == size
    }


def direction(bars):
    if len(bars) < 2:
        return 0
    a, b = list(bars)[-2:]
    if b.high > a.high and b.low > a.low:
        return 1
    if b.high < a.high and b.low < a.low:
        return -1
    return 0


def zones(bars, side, fvg):
    if not fvg:
        a = bars[-1]
        midpoint = (a.high + a.low) / 2
        return (a.low, midpoint) if side == 1 else (midpoint, a.high)
    if len(bars) < 3:
        return None
    a, _, b = bars
    if side == 1 and b.low > a.high:
        return a.high, b.low
    if side == -1 and b.high < a.low:
        return b.high, a.low
    return None


def setup_stream(bars):
    clocks = {tf: complete_buckets(bars, tf) for tf in (15, 60, 240)}
    history = {tf: deque(maxlen=3) for tf in clocks}
    prev = None
    for bar in bars:
        closed = bar.minute + 1
        for tf, lookup in clocks.items():
            if closed in lookup:
                history[tf].append(lookup[closed])
        if (prev and bar.minute == prev.minute + 1
                and all(history[tf] and history[tf][-1].minute + 2 * tf > closed for tf in clocks)):
            h4, h1 = (direction(history[tf]) for tf in (240, 60))
            for side in (1, -1):
                up = side == 1
                if not (bar.close > prev.high if up else bar.close < prev.low):
                    continue
                sweep = bar.low < prev.low if up else bar.high > prev.high
                if h4 == h1 == side:
                    kind = "trend"
                elif h4 == -side and h1 == side and sweep:
                    kind = "countertrend"
                else:
                    continue
                for variant in ("structure", "structure_fvg"):
                    zone = zones(history[15], side, variant == "structure_fvg")
                    if zone and bar.low <= zone[1] and bar.high >= zone[0]:
                        stop = min(zone[0], bar.low, prev.low) if up else max(zone[1], bar.high, prev.high)
                        yield variant, closed, side, kind, stop, zone
                        if variant == "structure" and kind == "trend" and closed % 15:
                            edge = zone[1] if up else zone[0]
                            if all((price - edge) * side > 0 for price in (prev.low if up else prev.high, bar.close)):
                                yield "structure_retest", closed, side, kind, stop, zone
        prev = bar


def replay(bars, signals, cost, move_after_tp1=False):
    position = None
    trades = []
    rejected = {}
    for bar in bars:
        signal = signals.get(bar.minute)
        if signal and position:
            rejected["position_open"] = rejected.get("position_open", 0) + 1
        if signal and position is None:
            side, kind, stop, zone = signal
            risk = (bar.open - stop) * side
            if risk <= 0 or risk <= 2 * cost:
                rejected["risk_or_cost"] = rejected.get("risk_or_cost", 0) + 1
            else:
                position = dict(side=side, kind=kind, entry=bar.open, stop=stop, zone=zone,
                                risk=risk, entry_minute=bar.minute, fills=[],
                                targets=[bar.open + side * risk * r for r in (1, 2, 3)])
        if position is None:
            continue
        side = position["side"]
        fills = position["fills"]
        moved = move_after_tp1 and bool(fills)
        stop = position["entry"] if moved else position["stop"]
        stop_reason = "SL_AT_ENTRY" if moved else "SL"
        adverse = bar.low if side == 1 else bar.high
        favorable = bar.high if side == 1 else bar.low
        if (adverse - stop) * side <= 0:
            stop_fill = bar.open if (bar.open - stop) * side <= 0 else stop
            fills.extend(dict(reason=stop_reason, price=stop_fill, minute=bar.minute) for _ in range(3 - len(fills)))
        else:
            for level, target in enumerate(position["targets"][len(fills):], start=len(fills) + 1):
                if (favorable - target) * side >= 0:
                    fills.append(dict(reason=f"TP{level}", price=target, minute=bar.minute))
        if len(fills) == 3:
            position["net_r"] = (sum((f["price"] - position["entry"]) * side for f in fills) / 3 - cost) / position["risk"]
            trades.append(position)
            position = None
    return trades, position, rejected


def stats(trades):
    values = [t["net_r"] for t in trades]
    wins = sum(r > 0 for r in values)
    losses = sum(r < 0 for r in values)
    equity = peak = drawdown = 0
    for r in values:
        equity += r
        peak = max(peak, equity)
        drawdown = max(drawdown, peak - equity)
    return dict(closed=len(values), wins=wins, losses=losses, breakeven=len(values) - wins - losses,
                win_rate=wins / len(values) if values else None,
                mean_net_r=sum(values) / len(values) if values else None,
                net_r=sum(values), closed_trade_drawdown_r=drawdown if values else None,
                average_win_to_loss_r=(sum(r for r in values if r > 0) / wins) /
                (-sum(r for r in values if r < 0) / losses) if wins and losses else None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv")
    parser.add_argument("--cost", action="append", type=float, required=True)
    args = parser.parse_args()
    if any(not math.isfinite(c) or c < 0 for c in args.cost):
        parser.error("--cost must be finite and nonnegative")
    bars = read_bars(args.csv)
    candidates = {"structure": {}, "structure_fvg": {}, "structure_retest": {}}
    for name, at, side, kind, stop, zone in setup_stream(bars):
        candidates[name][at] = (side, kind, stop, zone)
    report = dict(bars=len(bars), start_utc=datetime.fromtimestamp(bars[0].minute * 60, timezone.utc).isoformat(),
                  last_open_utc=datetime.fromtimestamp(bars[-1].minute * 60, timezone.utc).isoformat(),
                  missing_minutes=bars[-1].minute - bars[0].minute + 1 - len(bars),
                  complete_bars={tf: len(complete_buckets(bars, tf)) for tf in (15, 60, 240)}, runs=[])
    for name, signals in candidates.items():
        for cost in args.cost:
            for move_after_tp1 in (False, True):
                trades, open_trade, rejected = replay(bars, signals, cost, move_after_tp1)
                report["runs"].append(dict(variant=name, round_trip_cost=cost, signals=len(signals),
                    stop_policy="entry_after_tp1" if move_after_tp1 else "fixed",
                    rejected=rejected, unfilled_at_end=int(bars[-1].minute + 1 in signals),
                    overall=stats(trades), by_type={k: stats([t for t in trades if t["kind"] == k])
                        for k in ("trend", "countertrend")}, open_trade=open_trade, trades=trades))
    print(json.dumps(report, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
