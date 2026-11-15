// Rebuilds data/airports.json from the OurAirports "airports.csv" (public domain).
// Usage: node scripts/build-airport-lookup.mjs path/to/airports.csv
// Source: https://ourairports.com/data/  (file: airports.csv)
import { readFileSync, writeFileSync } from 'node:fs';
import { parseCsv } from './lib/csv.mjs';

const [header, ...rows] = parseCsv(readFileSync(process.argv[2], 'utf8'));
const col = Object.fromEntries(header.map((name, i) => [name, i]));
const rank = { large_airport: 3, medium_airport: 2, small_airport: 1 };
const best = new Map();
for (const row of rows) {
  const code = row[col.iata_code]?.trim().toUpperCase();
  const type = row[col.type];
  if (!/^[A-Z]{3}$/.test(code ?? '') || !rank[type]) continue;
  const lat = Number(row[col.latitude_deg]);
  const lon = Number(row[col.longitude_deg]);
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) continue;
  const entry = { rank: rank[type] + (row[col.scheduled_service] === 'yes' ? 0.5 : 0), name: row[col.name], city: row[col.municipality] || '', country: row[col.iso_country], lat: +lat.toFixed(4), lon: +lon.toFixed(4) };
  if (!best.has(code) || best.get(code).rank < entry.rank) best.set(code, entry);
}
const out = {};
for (const code of [...best.keys()].sort()) {
  const { rank: _rank, ...rest } = best.get(code);
  out[code] = rest;
}
writeFileSync('data/airports.json', JSON.stringify(out));
console.log(`Wrote data/airports.json with ${Object.keys(out).length} airports`);
