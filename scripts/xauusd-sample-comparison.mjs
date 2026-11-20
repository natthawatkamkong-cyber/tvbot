import { pathToFileURL } from 'node:url';
import { collectTicks } from './xauusd-stream-probe.mjs';
import { compareM1 } from './xauusd-compare-m1.mjs';

const minute = 60000;
const dateFormat = /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:00$/;

export async function sampleComparison({
  connect, readReference, tolerance = 0, clock = Date.now, durationMs = 15000,
}) {
  const startedAt = clock();
  const batch = await collectTicks(connect(), { durationMs });
  const endedAt = clock();
  const completedBefore = Math.floor(endedAt / minute) * minute;
  const requestedFrom = Math.floor(startedAt / minute) * minute;
  const payload = await readReference();
  if (payload?.status !== 'ok' || payload.meta?.symbol !== 'XAU/USD' ||
      payload.meta?.interval !== '1min' || !['UTC','Etc/UTC'].includes(payload.meta?.exchange_timezone) ||
      !Array.isArray(payload.values)) {
    throw new Error('Unverified UTC XAU/USD M1 reference response');
  }
  const reference = payload.values.flatMap(({ datetime, ...ohlc }) => {
    if (typeof datetime !== 'string' || !dateFormat.test(datetime)) throw new Error('Invalid M1 reference timestamp');
    const time = Date.parse(datetime.replace(' ', 'T') + 'Z');
    if (!Number.isFinite(time)) throw new Error('Invalid M1 reference timestamp');
    if (time < requestedFrom || time >= completedBefore) return [];
    return [{...ohlc, openTime:new Date(time).toISOString()}];
  });
  const byMinute = new Map();
  for (const {timestampMs, price} of [...batch.ticks].sort((a,b)=>a.timestampMs-b.timestampMs)) {
    if (timestampMs < requestedFrom || timestampMs >= endedAt) continue;
    const start = Math.floor(timestampMs / minute) * minute;
    const bar = byMinute.get(start);
    if (bar) {
      bar.high = Math.max(bar.high, price);
      bar.low = Math.min(bar.low, price);
      bar.close = price;
    } else {
      byMinute.set(start,{openTime:new Date(start).toISOString(),open:price,high:price,low:price,close:price});
    }
  }
  const series = {symbol:'XAUUSD',timeframe:'M1'};
  const comparison = compareM1({
    tolerance,
    stream:{...series,closed:[],provisional:[...byMinute.values()]},
    reference:{...series,closed:reference},
  });
  const referencesByTime = new Map(reference.map(bar => [bar.openTime, bar]));
  const sampleOverlap = [...byMinute.values()].flatMap(bar => {
    const referenceBar = referencesByTime.get(bar.openTime);
    return referenceBar ? [{openTime:bar.openTime, provisionalStream:bar, reference:referenceBar}] : [];
  });
  return {
    startedAt:new Date(startedAt).toISOString(), endedAt:new Date(endedAt).toISOString(),
    tickCount:batch.ticks.length, comparison, sampleOverlap,
  };
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try {
    const apiKey = process.env.TWELVE_DATA_API_KEY;
    if (!apiKey) throw new Error('Set TWELVE_DATA_API_KEY in the runtime environment');
    const socket = new URL('wss://ws.twelvedata.com/v1/quotes/price');
    socket.searchParams.set('apikey',apiKey);
    const report = await sampleComparison({
      connect:()=>new WebSocket(socket),
      readReference:async ()=>{
        const url = new URL('https://api.twelvedata.com/time_series');
        url.search = new URLSearchParams({symbol:'XAU/USD',interval:'1min',timezone:'UTC',outputsize:'5',apikey:apiKey});
        const response = await fetch(url,{signal:AbortSignal.timeout(10000)});
        if (!response.ok) throw new Error('Reference request failed with HTTP ' + response.status);
        return response.json();
      },
    });
    process.stdout.write(JSON.stringify(report,null,2)+'\n');
  } catch (error) {
    process.stderr.write(error.message+'\n');
    process.exitCode = 1;
  }
}
