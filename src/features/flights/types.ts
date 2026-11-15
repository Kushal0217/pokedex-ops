/** Shape of flights.data.json, written by scripts/import-flights.mjs. Flown legs only. */
export interface Flight {
  /** ISO date, YYYY-MM-DD. */
  date: string;
  /** May be empty when unknown. */
  airline: string;
  /** May be empty when unknown. */
  flightNumber: string;
  /** IATA codes. */
  origin: string;
  destination: string;
}

export interface AirportInfo {
  name: string;
  city: string;
  /** ISO 3166-1 alpha-2. */
  country: string;
  lat: number;
  lon: number;
}

export interface FlightData {
  flights: Flight[];
  /** Metadata for airports found in the local lookup. An airport missing here stays in the list but off the map. */
  airports: Record<string, AirportInfo>;
}
