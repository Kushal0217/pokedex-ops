import * as Tabs from '@radix-ui/react-tabs';
import { useEffect, useMemo, useState } from 'react';
import { RouteMap } from './RouteMap';
import { filterFlights, formatDate, placeName, routes as buildRoutes, totals as buildTotals, years as buildYears, type Route } from './flightStats';
import './flights.css';
import { loadFlights } from './loadFlights';
import type { Flight, FlightData } from './types';

function FlightRows({ data, flights, caption }: { data: FlightData; flights: Flight[]; caption: string }) {
  return (
    <table className="board">
      <caption className="visually-hidden">{caption}</caption>
      <thead>
        <tr>
          <th scope="col">Date</th>
          <th scope="col">Airline</th>
          <th scope="col">Flight</th>
          <th scope="col">From</th>
          <th scope="col">To</th>
        </tr>
      </thead>
      <tbody>
        {flights.map((f, i) => (
          <tr key={`${f.date}-${f.origin}-${f.destination}-${f.flightNumber}-${i}`}>
            <td data-label="Date">{formatDate(f.date)}</td>
            <td data-label="Airline">{f.airline || <span className="board__unknown">not recorded</span>}</td>
            <td data-label="Flight">{f.flightNumber || <span className="board__unknown">not recorded</span>}</td>
            <td data-label="From">{placeName(data, f.origin)}</td>
            <td data-label="To">{placeName(data, f.destination)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function RouteDetails({ data, route }: { data: FlightData; route: Route }) {
  const direction = (from: string, to: string, flights: Flight[]) =>
    flights.length > 0 && (
      <section>
        <h4 className="route-details__direction">
          {placeName(data, from)} → {placeName(data, to)}: {flights.length} {flights.length === 1 ? 'flight' : 'flights'}
        </h4>
        <FlightRows data={data} flights={flights} caption={`Flights from ${placeName(data, from)} to ${placeName(data, to)}`} />
      </section>
    );
  return (
    <div className="route-details" aria-live="polite">
      <h3 className="route-details__title">
        {route.a} ↔ {route.b} · flown {route.count} {route.count === 1 ? 'time' : 'times'}
      </h3>
      {!route.onMap && <p className="route-details__note">This route is not drawn on the map: one of its airports has no location on file.</p>}
      {direction(route.a, route.b, route.outbound)}
      {direction(route.b, route.a, route.inbound)}
    </div>
  );
}

/**
 * The airport's flight log: Route map and All flights over one imported
 * dataset. Loaded only when the airport is opened. With no data it shows a
 * deliberate empty state rather than zeros or sample flights.
 */
export default function FlightLog() {
  const [data, setData] = useState<FlightData | null>(null);
  const [failed, setFailed] = useState(false);
  const [tab, setTab] = useState('map');
  const [routeKey, setRouteKey] = useState<string | null>(null);
  const [year, setYear] = useState('all');
  const [search, setSearch] = useState('');

  useEffect(() => {
    let current = true;
    loadFlights().then((loaded) => current && setData(loaded), () => current && setFailed(true));
    return () => {
      current = false;
    };
  }, []);

  const routeList = useMemo(() => (data ? buildRoutes(data) : []), [data]);
  const stats = useMemo(() => (data ? buildTotals(data) : null), [data]);
  const yearList = useMemo(() => (data ? buildYears(data) : []), [data]);
  const shown = useMemo(() => (data ? filterFlights(data, year, search) : []), [data, year, search]);

  if (failed) return <p className="flight-log__status" role="alert">The flight log could not be loaded. Please try again.</p>;
  if (!data || !stats) return <p className="flight-log__status">Loading flight log…</p>;

  if (data.flights.length === 0) {
    return (
      <div className="flight-log__empty">
        <p className="flight-log__empty-title">No flights on the board yet</p>
        <p>Kushal’s flight history has not been added. When it is, a route map, the full list of flights and totals will appear here.</p>
      </div>
    );
  }

  const selectedRoute = routeList.find((r) => r.key === routeKey) ?? null;

  return (
    <div className="flight-log">
      <dl className="flight-totals">
        <div>
          <dt>Flights taken</dt>
          <dd>{stats.flights}</dd>
        </div>
        <div>
          <dt>Airports visited</dt>
          <dd>{stats.airports}</dd>
        </div>
        <div>
          <dt>Countries flown to/from</dt>
          <dd>{stats.countries}</dd>
        </div>
      </dl>
      <p className="flight-log__scope">
        Totals count the flights on this board only.
        {stats.airportsWithoutCountry > 0 && ` ${stats.airportsWithoutCountry} ${stats.airportsWithoutCountry === 1 ? 'airport has' : 'airports have'} no country on file and ${stats.airportsWithoutCountry === 1 ? 'is' : 'are'} not counted as a country.`}
      </p>

      <Tabs.Root value={tab} onValueChange={setTab}>
        <Tabs.List className="projects__tabs flight-log__tabs" aria-label="Flight log views">
          <Tabs.Trigger className="projects__tab" value="map">
            Route map
          </Tabs.Trigger>
          <Tabs.Trigger className="projects__tab" value="list">
            All flights
          </Tabs.Trigger>
        </Tabs.List>

        <Tabs.Content className="flight-log__panel" value="map">
          <RouteMap data={data} routes={routeList} selectedKey={routeKey} onSelect={setRouteKey} />
          <p className="flight-log__hint">Pick a route to see its flights. Every flight is also in “All flights”.</p>
          <ul className="route-buttons">
            {routeList.map((route) => (
              <li key={route.key}>
                <button type="button" className="route-button" aria-pressed={route.key === routeKey} onClick={() => setRouteKey(route.key)}>
                  {route.a} ↔ {route.b}
                  <span className="route-button__count">
                    {route.count} {route.count === 1 ? 'flight' : 'flights'}
                    {!route.onMap && ' · not on map'}
                  </span>
                </button>
              </li>
            ))}
          </ul>
          {selectedRoute && <RouteDetails data={data} route={selectedRoute} />}
        </Tabs.Content>

        <Tabs.Content className="flight-log__panel" value="list">
          <div className="flight-filters">
            <label>
              <span>Search city or airport code</span>
              <input type="search" value={search} onChange={(e) => setSearch(e.target.value)} autoComplete="off" spellCheck={false} />
            </label>
            <label>
              <span>Year</span>
              <select value={year} onChange={(e) => setYear(e.target.value)}>
                <option value="all">All years</option>
                {yearList.map((y) => (
                  <option key={y} value={y}>
                    {y}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <p className="flight-log__count" role="status">
            Showing {shown.length} of {data.flights.length} flights
          </p>
          {shown.length > 0 ? <FlightRows data={data} flights={shown} caption="Flights taken, newest first" /> : <p className="flight-log__none">No flights match that search.</p>}
        </Tabs.Content>
      </Tabs.Root>
    </div>
  );
}
