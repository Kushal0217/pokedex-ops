import '../places.css';

/** Stadium, before the penalty game exists (Slices 7-8). States plainly what is and is not here yet. */
export function StadiumPreview() {
  return (
    <div className="place-panel">
      <p className="place-panel__kicker">Barcelona is Kushal’s club.</p>
      <p className="place-panel__later">
        <strong>Not built yet:</strong> an optional penalty shootout is planned for this stadium. Nothing else on the
        site depends on it.
      </p>
    </div>
  );
}
