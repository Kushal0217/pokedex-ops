// Run with: npm test
// Uses synthetic fixture data only. Nothing here is real travel history.
import assert from 'node:assert/strict';
import { execFileSync, spawnSync } from 'node:child_process';
import { mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';
import { parseCsv } from '../lib/csv.mjs';
import { ImportError, importFlights } from '../lib/flights-import.mjs';

const lookup = JSON.parse(readFileSync(new URL('../../data/airports.json', import.meta.url), 'utf8'));
const fixture = readFileSync(new URL('../fixtures/flights/synthetic-flights.csv', import.meta.url), 'utf8');
const HEADER = 'date,airline,flight_number,origin_airport,destination_airport,status';
const run = (csv) => importFlights(csv, lookup, { today: '2026-11-15' });

test('CSV parser: quotes, escaped quotes, embedded commas and newlines, CRLF, BOM', () => {
  assert.deepEqual(parseCsv('﻿a,b\r\n"x, y","say ""hi"""\r\n"two\nlines",z\n\n'), [['a', 'b'], ['x, y', 'say "hi"'], ['two\nlines', 'z']]);
  assert.throws(() => parseCsv('a,b\n"open,1'), /never closed/);
});

test('only flown legs are published; booked, canceled and uncertain are excluded', () => {
  const { data, report } = run(fixture);
  assert.equal(data.flights.length, 10);
  assert.deepEqual(report.excludedByStatus, { booked: 1, canceled: 2, uncertain: 1 });
  assert.ok(data.flights.every((f) => f.date <= '2024-02-10'));
});

test('quoted and UTF-8 fields survive; codes and statuses are normalised', () => {
  const { data } = run(fixture);
  const airlines = data.flights.map((f) => f.airline);
  assert.ok(airlines.includes('SYNTHETIC Air, Long-Haul Division'));
  assert.ok(airlines.includes('SYNTHETIC "Quoted" Air'));
  assert.ok(airlines.includes('SYNTHETIC Aír Ünïcode'));
  assert.ok(data.flights.every((f) => /^[A-Z]{3}$/.test(f.origin) && /^[A-Z]{3}$/.test(f.destination)));
});

test('invalid records are excluded and explained, line by line', () => {
  const { report } = run(fixture);
  const byLine = Object.fromEntries(report.invalidRows.map((r) => [r.line, r.problems.join('; ')]));
  assert.match(byLine[17], /date does not exist/);
  assert.match(byLine[18], /not a three-letter IATA code/);
  assert.match(byLine[19], /unknown status "landed"/);
  assert.match(byLine[20], /origin and destination are the same/);
  assert.match(byLine[21], /in the future/);
  assert.match(byLine[22], /has 3 fields/);
  assert.equal(report.invalidRows.length, 6);
});

test('duplicates: same flight number is removed once; uncertain same-route legs are both kept and flagged', () => {
  const { data, report } = run(fixture);
  // lines 6 and 7 are the same leg written two ways (ZZ 101 / zz-101)
  assert.deepEqual(report.duplicatesRemoved.map((d) => [d.line, d.duplicateOfLine]), [[7, 6]]);
  assert.equal(data.flights.filter((f) => f.date === '2023-01-15').length, 1);
  // lines 8 and 9: same date and route, flight number missing -> not merged
  assert.deepEqual(report.possibleDuplicatesKept.map((d) => d.lines), [[8, 9]]);
  assert.equal(data.flights.filter((f) => f.date === '2023-01-20').length, 2);
  // the same flight number on a different date is a different flight
  assert.equal(data.flights.filter((f) => f.flightNumber === 'ZZ 101').length, 2);
});

test('unknown airports keep their flight in the list but get no invented coordinates', () => {
  const { data, report } = run(fixture);
  assert.deepEqual(report.airportsMissingMetadata, ['QQQ']);
  assert.ok(data.flights.some((f) => f.destination === 'QQQ'));
  assert.equal(data.airports.QQQ, undefined);
  assert.deepEqual(Object.keys(data.airports), ['DFW', 'HYD', 'LHR', 'ORD']);
  assert.equal(data.airports.LHR.country, 'GB');
});

test('only the six known columns are read; extra columns are reported and never published', () => {
  const { data, report } = run(`seat,${HEADER},booking_ref\n12A,2020-01-02,SYNTHETIC Air,ZZ 1,DFW,ORD,flown,SECRET99\n`);
  assert.deepEqual(report.ignoredColumns, ['seat', 'booking_ref']);
  assert.ok(!JSON.stringify(data).includes('SECRET99') && !JSON.stringify(data).includes('12A'));
  assert.deepEqual(data.flights, [{ date: '2020-01-02', airline: 'SYNTHETIC Air', flightNumber: 'ZZ 1', origin: 'DFW', destination: 'ORD' }]);
});

test('file-level problems throw instead of producing data', () => {
  assert.throws(() => run(''), ImportError);
  assert.throws(() => run('date,airline,origin_airport,destination_airport,status\n'), /Missing column\(s\): flight_number/);
  assert.throws(() => run(`${HEADER}\n2020-01-02,"SYNTHETIC,ZZ 1,DFW,ORD,flown\n`), /never closed/);
});

test('a header-only template is valid and empty', () => {
  const template = readFileSync(new URL('../../source-assets/flights_template.csv', import.meta.url), 'utf8');
  assert.deepEqual(run(template).data, { flights: [], airports: {} });
});

test('CLI: a malformed or emptying replacement leaves the previous data file untouched', () => {
  const dir = mkdtempSync(join(tmpdir(), 'flights-'));
  const out = join(dir, 'flights.data.json');
  const cli = new URL('../import-flights.mjs', import.meta.url).pathname;
  const good = join(dir, 'good.csv');
  writeFileSync(good, `${HEADER}\n2020-01-02,SYNTHETIC Air,ZZ 1,DFW,ORD,flown\n`);
  execFileSync('node', [cli, good, '--out', out], { cwd: dir });
  const before = readFileSync(out, 'utf8');
  assert.equal(JSON.parse(before).flights.length, 1);

  for (const [name, content] of [['broken-quote.csv', `${HEADER}\n2020-01-02,"oops,ZZ 1,DFW,ORD,flown\n`], ['wrong-header.csv', 'when,who\n1,2\n'], ['header-only.csv', `${HEADER}\n`], ['all-invalid.csv', `${HEADER}\nnot-a-date,x,y,DFW,ORD,flown\n`]]) {
    const bad = join(dir, name);
    writeFileSync(bad, content);
    const result = spawnSync('node', [cli, bad, '--out', out], { cwd: dir, encoding: 'utf8' });
    assert.notEqual(result.status, 0, `${name} should fail`);
    assert.match(result.stderr, /left unchanged/);
    assert.equal(readFileSync(out, 'utf8'), before, `${name} must not change the data file`);
  }
  // An intentional wipe is still possible.
  execFileSync('node', [cli, join(dir, 'header-only.csv'), '--out', out, '--allow-empty'], { cwd: dir });
  assert.equal(JSON.parse(readFileSync(out, 'utf8')).flights.length, 0);
});
