import type { Flight, FlightData } from './types';

export interface Totals {
  /** Flight legs, not bookings. */
  flights: number;
  /** Distinct departure/arrival airports. */
  airports: number;
  /** Distinct countries of those airports ("flown to/from", not "visited"). */
  countries: number;
  /** Airports with no country on file; they are not counted as a country. */
  airportsWithoutCountry: number;
}

export function totals(data: FlightData): Totals {
  const codes = new Set(data.flights.flatMap((f) => [f.origin, f.destination]));
  const countries = new Set<string>();
  let missing = 0;
  for (const code of codes) {
    const country = data.airports[code]?.country;
    if (country) countries.add(country);
    else missing += 1;
  }
  return { flights: data.flights.length, airports: codes.size, countries: countries.size, airportsWithoutCountry: missing };
}

export interface Route {
  /** Stable key: the two codes in alphabetical order, e.g. "DFW-ORD". */
  key: string;
  a: string;
  b: string;
  /** Flights from a to b, and from b to a, newest first. */
  outbound: Flight[];
  inbound: Flight[];
  count: number;
  /** True when both airports have coordinates. */
  onMap: boolean;
}

const newestFirst = (x: Flight, y: Flight) => y.date.localeCompare(x.date);

/** Groups flights into undirected routes, keeping each direction separate inside the route. */
export function routes(data: FlightData): Route[] {
  const map = new Map<string, Route>();
  for (const flight of data.flights) {
    const [a, b] = [flight.origin, flight.destination].sort() as [string, string];
    const key = `${a}-${b}`;
    const route = map.get(key) ?? { key, a, b, outbound: [], inbound: [], count: 0, onMap: Boolean(data.airports[a] && data.airports[b]) };
    (flight.origin === a ? route.outbound : route.inbound).push(flight);
    route.count += 1;
    map.set(key, route);
  }
  for (const route of map.values()) {
    route.outbound.sort(newestFirst);
    route.inbound.sort(newestFirst);
  }
  return [...map.values()].sort((x, y) => y.count - x.count || x.key.localeCompare(y.key));
}

export const years = (data: FlightData): string[] => [...new Set(data.flights.map((f) => f.date.slice(0, 4)))].sort().reverse();

/** Year filter plus search over airport code, city and airport name of either end. */
export function filterFlights(data: FlightData, year: string, search: string): Flight[] {
  const needle = search.trim().toLowerCase();
  const haystack = (code: string) => {
    const info = data.airports[code];
    return `${code} ${info?.city ?? ''} ${info?.name ?? ''}`.toLowerCase();
  };
  return data.flights
    .filter((f) => (year === 'all' || f.date.startsWith(year)) && (needle === '' || haystack(f.origin).includes(needle) || haystack(f.destination).includes(needle)))
    .sort(newestFirst);
}

/** "Chicago (ORD)" when the city is known, otherwise just the code. */
export const placeName = (data: FlightData, code: string) => (data.airports[code]?.city ? `${data.airports[code]!.city} (${code})` : code);

const dateFormat = new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' });
export const formatDate = (iso: string) => dateFormat.format(new Date(`${iso}T00:00:00Z`));
