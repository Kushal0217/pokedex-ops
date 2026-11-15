import '../places.css';

/** Airport, before the flight log exists (Slice 6). No flights, routes or totals are shown or implied. */
export function AirportPreview() {
  return (
    <div className="place-panel">
      <p className="place-panel__kicker">Flight log</p>
      <p className="place-panel__later">
        <strong>Not built yet:</strong> a route map and a list of flights Kushal has taken are planned for this
        terminal. No flight history has been added so far.
      </p>
    </div>
  );
}
