import { readFile } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';

const fields = ['open', 'high', 'low', 'close'];

function indexCandles(candles, label) {
  if (!Array.isArray(candles)) throw new Error(`Expected ${label} candle array`);
  const indexed = new Map();
  for (const candle of candles) {
    const timestamp = typeof candle?.openTime === 'string' && candle.openTime.endsWith('Z')
      ? Date.parse(candle.openTime)
      : NaN;
    if (!Number.isFinite(timestamp) || timestamp % 60000 !== 0 || indexed.has(timestamp)) {
      throw new Error(`Invalid or duplicate ${label} M1 open time`);
    }
    const values = Object.fromEntries(fields.map(field => {
      const raw = candle[field];
      const value = typeof raw === 'string' && /^\d+(?:\.\d+)?$/.test(raw) ? Number(raw) : raw;
      if (!Number.isFinite(value) || value <= 0) throw new Error(`Invalid ${label} ${field}`);
      return [field, value];
    }));
    if (values.low > Math.min(values.open, values.close) || values.high < Math.max(values.open, values.close)) {
      throw new Error(`Invalid ${label} OHLC range`);
    }
    indexed.set(timestamp, values);
  }
  return indexed;
}

export function compareM1({ stream, reference, tolerance }) {
  if (stream?.symbol !== 'XAUUSD' || stream.timeframe !== 'M1' ||
      reference?.symbol !== 'XAUUSD' || reference.timeframe !== 'M1' ||
      !Number.isFinite(tolerance) || tolerance < 0) {
    throw new Error('Expected XAUUSD M1 candle sets and a nonnegative price tolerance');
  }
  const closed = indexCandles(stream.closed, 'stream closed');
  const provisional = indexCandles(stream.provisional, 'stream provisional');
  const baseline = indexCandles(reference.closed, 'reference closed');
  const rows = [];
  const timestamps = [...new Set([...closed.keys(), ...provisional.keys(), ...baseline.keys()])].sort((a,b) => a-b);
  for (const timestamp of timestamps) {
    const openTime = new Date(timestamp).toISOString();
    const observed = closed.get(timestamp);
    const expected = baseline.get(timestamp);
    if (observed && provisional.has(timestamp)) throw new Error('Stream candle is both closed and provisional');
    if (provisional.has(timestamp)) {
      rows.push({openTime, status:'PROVISIONAL'});
      continue;
    }
    if (!observed || !expected) {
      rows.push({openTime, status:observed ? 'REFERENCE_MISSING' : 'STREAM_MISSING'});
      continue;
    }
    const delta = Object.fromEntries(fields.map(field => [field, observed[field] - expected[field]]));
    const match = fields.every(field => Math.abs(delta[field]) <= tolerance);
    rows.push({openTime, status:match ? 'MATCH' : 'MISMATCH', delta});
  }
  const counts = {MATCH:0,MISMATCH:0,PROVISIONAL:0,REFERENCE_MISSING:0,STREAM_MISSING:0};
  for (const row of rows) counts[row.status]++;
  return { tolerance, comparableBars:counts.MATCH+counts.MISMATCH, counts, rows };
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try {
    const [file] = process.argv.slice(2);
    if (!file) throw new Error('Usage: node xauusd-compare-m1.mjs comparison-input.json');
    const input = JSON.parse(await readFile(file, 'utf8'));
    process.stdout.write(JSON.stringify(compareM1(input), null, 2) + '\n');
  } catch (error) {
    process.stderr.write(error.message + '\n');
    process.exitCode = 1;
  }
}
