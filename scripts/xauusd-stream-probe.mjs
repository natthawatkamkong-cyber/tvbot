import { pathToFileURL } from 'node:url';

const symbol = 'XAU/USD';
const endpoint = 'wss://ws.twelvedata.com/v1/quotes/price';

export function collectTicks(socket, { durationMs = 15000, maxTicks = 2000 } = {}) {
  return new Promise((resolve, reject) => {
    const ticks = [];
    let complete = false;
    let heartbeat;
    const timeout = setTimeout(() => finish(), durationMs);

    function finish(error) {
      if (complete) return;
      complete = true;
      clearTimeout(timeout);
      clearInterval(heartbeat);
      socket.close();
      if (error || !ticks.length) {
        reject(error ?? new Error('No XAU/USD ticks received during the sample'));
        return;
      }
      // A sampled stream does not prove that any minute has complete coverage.
      resolve({ symbol, ticks, completeThroughMs: 0 });
    }

    socket.addEventListener('open', () => {
      if (complete) return;
      socket.send(JSON.stringify({ action: 'subscribe', params: { symbols: symbol } }));
      heartbeat = setInterval(() => {
        if (socket.readyState === 1) socket.send(JSON.stringify({ action: 'heartbeat' }));
      }, 10000);
    });
    socket.addEventListener('message', ({ data }) => {
      if (complete) return;
      let event;
      try {
        event = JSON.parse(data);
      } catch {
        finish(new Error('Malformed WebSocket response'));
        return;
      }
      if (event?.status === 'error') {
        finish(new Error('Twelve Data rejected the stream request'));
        return;
      }
      if (event?.event !== 'price' || event.symbol !== symbol) return;
      const timestampMs = event.timestamp * 1000;
      if (!Number.isSafeInteger(event.timestamp) || !Number.isSafeInteger(timestampMs) || timestampMs <= 0 ||
          !Number.isFinite(event.price) || event.price <= 0) {
        finish(new Error('Invalid XAU/USD price event'));
        return;
      }
      ticks.push({ timestampMs, price: event.price });
      if (ticks.length >= maxTicks) finish();
    });
    socket.addEventListener('close', () => finish(new Error('Price stream disconnected before the sample completed')));
    socket.addEventListener('error', () => finish(new Error('Price stream connection failed')));
  });
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try {
    const apiKey = process.env.TWELVE_DATA_API_KEY;
    if (!apiKey) throw new Error('Set TWELVE_DATA_API_KEY before running the probe');
    const url = new URL(endpoint);
    url.searchParams.set('apikey', apiKey);
    const batch = await collectTicks(new WebSocket(url));
    process.stdout.write(JSON.stringify(batch) + '\n');
  } catch (error) {
    process.stderr.write((error instanceof Error ? error.message : 'Price probe failed') + '\n');
    process.exitCode = 1;
  }
}
