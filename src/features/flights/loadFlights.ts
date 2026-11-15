import type { FlightData } from './types';

/**
 * Loads the approved flight data (flights.data.json, produced by
 * `npm run import:flights`). The site never reads the source CSV.
 *
 * Development only: `?fixture=flights` on the dev server loads synthetic data
 * generated from scripts/fixtures/flights/synthetic-flights.csv. It is not real
 * travel history and is never part of a production build.
 */
export async function loadFlights(): Promise<FlightData> {
  if (import.meta.env.DEV && new URLSearchParams(window.location.search).get('fixture') === 'flights') {
    return (await import('./dev/flights.fixture.json')).default as FlightData;
  }
  return (await import('./flights.data.json')).default as FlightData;
}
