import { readFile } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';

const fields = ['OPEN', 'HIGH', 'LOW', 'CLOSE'];
const dateTime = /^(\d{4})\.(\d{2})\.(\d{2}) (\d{2}):(\d{2}):00$/;
const decimal = /^\d+(?:\.\d+)?$/;

export function importMt5M1(text, utcOffsetMinutes) {
  if (!Number.isInteger(utcOffsetMinutes) || Math.abs(utcOffsetMinutes) > 14 * 60) {
    throw new Error('Specify the verified UTC offset in minutes for this export');
  }
  const [header, ...rows] = text.replace(/^\uFEFF/, '').trim().split(/\r?\n/);
  const separator = header.includes('\t') ? '\t' : ',';
  const columns = header.split(separator).map(value => value.trim().replace(/^<(.+)>$/, '$1').toUpperCase());
  const required = ['DATE', 'TIME', ...fields];
  if (required.some(name => columns.filter(column => column === name).length !== 1) || !rows.length) {
    throw new Error('Expected MT5 DATE, TIME and OHLC columns with at least one M1 candle');
  }
  const offsets = Object.fromEntries(required.map(name => [name, columns.indexOf(name)]));
  const candles = new Map();
  for (const [index, line] of rows.entries()) {
    const record = line.split(separator);
    const parts = dateTime.exec(record[offsets.DATE]?.trim() + ' ' + record[offsets.TIME]?.trim());
    const local = parts ? `${parts[1]}-${parts[2]}-${parts[3]}T${parts[4]}:${parts[5]}:00.000Z` : '';
    const timestamp = Date.parse(local);
    if (!Number.isFinite(timestamp) || new Date(timestamp).toISOString() !== local) {
      throw new Error('Invalid minute timestamp on row ' + (index + 2));
    }
    const openMs = timestamp - utcOffsetMinutes * 60000;
    const prices = fields.map(field => {
      const value = record[offsets[field]]?.trim();
      return decimal.test(value) ? Number(value) : NaN;
    });
    const [open, high, low, close] = prices;
    if (!prices.every(price => Number.isFinite(price) && price > 0) ||
        high < Math.max(open, close) || low > Math.min(open, close) || candles.has(openMs)) {
      throw new Error('Invalid OHLC or duplicate minute on row ' + (index + 2));
    }
    candles.set(openMs, {openTime:new Date(openMs).toISOString(),closeTime:new Date(openMs+60000).toISOString(),open,high,low,close});
  }
  return [...candles.values()].sort((a,b)=>a.openTime.localeCompare(b.openTime));
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try {
    const [file, offset] = process.argv.slice(2);
    if (!file || !/^[+-]?\d+$/.test(offset ?? '')) {
      throw new Error('Usage: node xauusd-import-mt5-m1.mjs XAUUSD-M1.csv broker-utc-offset-minutes');
    }
    const raw = await readFile(file);
    const text = raw[0] === 255 && raw[1] === 254 ? raw.toString('utf16le') : raw.toString('utf8');
    process.stdout.write(JSON.stringify({candles:importMt5M1(text,Number(offset))},null,2)+'\n');
  } catch (error) {
    process.stderr.write(error.message+'\n');
    process.exitCode = 1;
  }
}
