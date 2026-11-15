/**
 * Flight CSV -> site data. Pure functions; the CLI wrapper is scripts/import-flights.mjs.
 *
 * Expected columns: date,airline,flight_number,origin_airport,destination_airport,status
 *  - one row per flight leg; ISO dates (YYYY-MM-DD); three-letter IATA codes
 *  - status: flown | booked | canceled | uncertain. Only `flown` rows are published.
 *  - only the six known columns are ever read, so any other column (seat, booking
 *    reference, ...) cannot reach the site; its presence is reported.
 *
 * A file-level problem throws ImportError and nothing is written. Row-level
 * problems exclude that row and are listed in the report.
 */
import { parseCsv } from './csv.mjs';

export const COLUMNS = ['date', 'airline', 'flight_number', 'origin_airport', 'destination_airport', 'status'];
export const STATUSES = ['flown', 'booked', 'canceled', 'uncertain'];

export class ImportError extends Error {}

function validDate(text, today) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(text)) return 'date is not YYYY-MM-DD';
  const [y, m, d] = text.split('-').map(Number);
  const date = new Date(Date.UTC(y, m - 1, d));
  if (date.getUTCFullYear() !== y || date.getUTCMonth() !== m - 1 || date.getUTCDate() !== d) return 'date does not exist';
  if (text > today) return 'date is in the future, so the flight cannot have been flown';
  return null;
}

const clean = (value) => (value ?? '').normalize('NFC').replace(/\s+/g, ' ').trim();
const flightNumberKey = (value) => value.replace(/[\s-]/g, '').toUpperCase();

/**
 * @param {string} csvText
 * @param {Record<string, {name:string, city:string, country:string, lat:number, lon:number}>} airportLookup
 * @param {{today?: string}} [options] today as YYYY-MM-DD (defaults to the current UTC date)
 */
export function importFlights(csvText, airportLookup, options = {}) {
  const today = options.today ?? new Date().toISOString().slice(0, 10);
  let rows;
  try {
    rows = parseCsv(csvText);
  } catch (error) {
    throw new ImportError(error.message);
  }
  if (rows.length === 0) throw new ImportError('The file is empty: expected a header row');
  const header = rows[0].map((name) => clean(name).toLowerCase());
  const missing = COLUMNS.filter((name) => !header.includes(name));
  if (missing.length > 0) throw new ImportError(`Missing column(s): ${missing.join(', ')}. Expected header: ${COLUMNS.join(',')}`);
  const index = Object.fromEntries(COLUMNS.map((name) => [name, header.indexOf(name)]));
  const ignoredColumns = header.filter((name) => !COLUMNS.includes(name));

  const report = {
    rowsRead: rows.length - 1,
    published: 0,
    excludedByStatus: { booked: 0, canceled: 0, uncertain: 0 },
    invalidRows: [],
    duplicatesRemoved: [],
    possibleDuplicatesKept: [],
    airportsMissingMetadata: [],
    ignoredColumns,
  };

  const flown = [];
  rows.slice(1).forEach((cells, i) => {
    const line = i + 2; // 1-based, counting the header
    const get = (name) => clean(cells[index[name]]);
    const problems = [];
    if (cells.length < header.length) problems.push(`has ${cells.length} fields, expected ${header.length}`);
    const date = get('date');
    const dateProblem = validDate(date, today);
    let status = get('status').toLowerCase();
    if (status === 'cancelled') status = 'canceled';
    if (!STATUSES.includes(status)) problems.push(`unknown status "${get('status')}"`);
    const origin = get('origin_airport').toUpperCase();
    const destination = get('destination_airport').toUpperCase();
    if (!/^[A-Z]{3}$/.test(origin)) problems.push(`origin "${get('origin_airport')}" is not a three-letter IATA code`);
    if (!/^[A-Z]{3}$/.test(destination)) problems.push(`destination "${get('destination_airport')}" is not a three-letter IATA code`);
    if (origin && origin === destination) problems.push('origin and destination are the same');
    // A bad date only matters for rows that would be published.
    if (dateProblem && (status === 'flown' || !STATUSES.includes(status))) problems.push(dateProblem);
    if (problems.length > 0) {
      report.invalidRows.push({ line, problems });
      return;
    }
    if (status !== 'flown') {
      report.excludedByStatus[status] += 1;
      return;
    }
    flown.push({ line, date, airline: get('airline'), flightNumber: get('flight_number'), origin, destination });
  });

  // Likely duplicates: same date and route. Identical flight numbers are the same leg;
  // anything less certain is kept and flagged for a person to review.
  const groups = new Map();
  for (const flight of flown) {
    const key = `${flight.date}|${flight.origin}|${flight.destination}`;
    groups.set(key, [...(groups.get(key) ?? []), flight]);
  }
  const kept = [];
  for (const group of groups.values()) {
    const seenNumbers = new Map();
    const survivors = [];
    for (const flight of group) {
      const number = flightNumberKey(flight.flightNumber);
      if (number && seenNumbers.has(number)) {
        report.duplicatesRemoved.push({ line: flight.line, duplicateOfLine: seenNumbers.get(number), flight: describe(flight) });
        continue;
      }
      if (number) seenNumbers.set(number, flight.line);
      survivors.push(flight);
    }
    if (survivors.length > 1 && survivors.some((f) => !flightNumberKey(f.flightNumber))) {
      report.possibleDuplicatesKept.push({ lines: survivors.map((f) => f.line), flight: describe(survivors[0]) });
    }
    kept.push(...survivors);
  }
  kept.sort((a, b) => a.date.localeCompare(b.date) || a.line - b.line);

  const airports = {};
  const missingAirports = new Set();
  for (const flight of kept) {
    for (const code of [flight.origin, flight.destination]) {
      const found = airportLookup[code];
      if (found) airports[code] = { name: found.name, city: found.city, country: found.country, lat: found.lat, lon: found.lon };
      else missingAirports.add(code);
    }
  }
  report.airportsMissingMetadata = [...missingAirports].sort();
  report.published = kept.length;

  const data = {
    flights: kept.map(({ date, airline, flightNumber, origin, destination }) => ({ date, airline, flightNumber, origin, destination })),
    airports: Object.fromEntries(Object.entries(airports).sort(([a], [b]) => a.localeCompare(b))),
  };
  return { data, report };
}

const describe = (f) => `${f.date} ${f.origin}-${f.destination}${f.flightNumber ? ' ' + f.flightNumber : ''}`;

export function formatReport(report) {
  const lines = [
    `Rows read: ${report.rowsRead}`,
    `Published (flown): ${report.published}`,
    `Excluded by status: booked ${report.excludedByStatus.booked}, canceled ${report.excludedByStatus.canceled}, uncertain ${report.excludedByStatus.uncertain}`,
  ];
  if (report.ignoredColumns.length) lines.push(`Ignored extra columns (never published): ${report.ignoredColumns.join(', ')}`);
  if (report.invalidRows.length) {
    lines.push(`Invalid rows excluded: ${report.invalidRows.length}`);
    for (const row of report.invalidRows) lines.push(`  line ${row.line}: ${row.problems.join('; ')}`);
  }
  if (report.duplicatesRemoved.length) {
    lines.push(`Duplicates removed (same date, route and flight number): ${report.duplicatesRemoved.length}`);
    for (const d of report.duplicatesRemoved) lines.push(`  line ${d.line} duplicates line ${d.duplicateOfLine}: ${d.flight}`);
  }
  if (report.possibleDuplicatesKept.length) {
    lines.push(`Possible duplicates KEPT for review (same date and route, flight number missing): ${report.possibleDuplicatesKept.length}`);
    for (const d of report.possibleDuplicatesKept) lines.push(`  lines ${d.lines.join(', ')}: ${d.flight}`);
  }
  if (report.airportsMissingMetadata.length) {
    lines.push(`Airports without map data (flights stay in the list, not on the map or in the country count): ${report.airportsMissingMetadata.join(', ')}`);
    lines.push('  Fix: correct the code in the CSV, or add the airport to data/airports.json, then import again.');
  }
  return lines.join('\n');
}
