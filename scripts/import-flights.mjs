// Imports the flight CSV into the site's data file.
//
//   node scripts/import-flights.mjs [csv] [--out file] [--allow-empty]
//
// Defaults: csv = private/flights.csv (git-ignored, never built),
//           out = src/features/flights/flights.data.json
//
// The output is replaced only when the whole import succeeds. A malformed
// file, or a file that would wipe existing flights, leaves it untouched.
import { existsSync, mkdirSync, readFileSync, renameSync, writeFileSync } from 'node:fs';
import { dirname } from 'node:path';
import { ImportError, formatReport, importFlights } from './lib/flights-import.mjs';

const args = process.argv.slice(2);
const flag = (name) => args.includes(name);
const option = (name, fallback) => (args.includes(name) ? args[args.indexOf(name) + 1] : fallback);
const positional = args.filter((a, i) => !a.startsWith('--') && args[i - 1] !== '--out');
const csvPath = positional[0] ?? 'private/flights.csv';
const outPath = option('--out', 'src/features/flights/flights.data.json');

function fail(message) {
  console.error(`Import failed: ${message}\nThe existing flight data was left unchanged.`);
  process.exit(1);
}

if (!existsSync(csvPath)) fail(`${csvPath} not found. Put the reviewed CSV there (see README, "Flights").`);
const lookup = JSON.parse(readFileSync(new URL('../data/airports.json', import.meta.url), 'utf8'));

let result;
try {
  result = importFlights(readFileSync(csvPath, 'utf8'), lookup);
} catch (error) {
  if (error instanceof ImportError) fail(error.message);
  throw error;
}

const previous = existsSync(outPath) ? JSON.parse(readFileSync(outPath, 'utf8')) : { flights: [] };
if (result.data.flights.length === 0 && previous.flights.length > 0 && !flag('--allow-empty')) {
  fail(`the new file has no publishable flights but the site currently has ${previous.flights.length}. Re-run with --allow-empty if that is intended.`);
}

const text = formatReport(result.report);
console.log(text);
mkdirSync(dirname(outPath), { recursive: true });
writeFileSync(`${outPath}.tmp`, JSON.stringify(result.data, null, 2) + '\n');
renameSync(`${outPath}.tmp`, outPath);
if (existsSync('private')) writeFileSync('private/flights-import-report.txt', text + '\n');
console.log(`\nWrote ${outPath} (${result.data.flights.length} flights, ${Object.keys(result.data.airports).length} airports). Rebuild the site to publish.`);
