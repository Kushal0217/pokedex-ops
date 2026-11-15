import { lazy, Suspense } from 'react';
import '../places.css';

// The flight log (data, world map and views) is its own chunk, fetched when the airport opens.
const FlightLog = lazy(() => import('./FlightLog'));

/** Airport interior: a small illustrated terminal strip above the flight log. */
export function AirportScene() {
  return (
    <div className="airport">
      <svg className="airport__art" viewBox="0 0 480 84" aria-hidden="true" focusable="false">
        <rect width={480} height={84} fill="#cfe4ee" />
        <rect y={60} width={480} height={24} fill="#b9b1a2" />
        <g shapeRendering="crispEdges" fill="#a8a092">
          {[40, 120, 200, 280, 360, 440].map((x) => <rect key={x} x={x} y={60} width={2} height={24} />)}
        </g>
        {/* tall windows with a plane outside */}
        {[16, 132, 248, 364].map((x) => <rect key={x} x={x} y={8} width={100} height={46} fill="#a8d6e6" stroke="#33241f" strokeWidth={3} />)}
        <g shapeRendering="crispEdges" fill="#fbf9f4" stroke="#33241f" strokeWidth={1.5}>
          <rect x={270} y={28} width={56} height={10} />
          <rect x={326} y={30} width={8} height={6} />
          <rect x={286} y={38} width={18} height={6} />
          <rect x={266} y={18} width={10} height={12} />
        </g>
        <rect x={268} y={20} width={6} height={6} fill="#c6452f" />
        <g fill="#dff2f7" opacity={0.6}>
          <path d="M 22 44 L 50 12 H 62 L 34 44 Z" />
          <path d="M 372 44 L 400 12 H 408 L 380 44 Z" />
        </g>
        {/* row of seats and a suitcase */}
        {[30, 58, 86].map((x) => (
          <g key={x}>
            <rect x={x} y={46} width={22} height={18} rx={3} fill="#2c467a" stroke="#33241f" strokeWidth={2} />
            <rect x={x + 3} y={64} width={3} height={10} fill="#33241f" />
            <rect x={x + 16} y={64} width={3} height={10} fill="#33241f" />
          </g>
        ))}
        <rect x={150} y={52} width={20} height={24} rx={2} fill="#c6452f" stroke="#33241f" strokeWidth={2} />
        <rect x={156} y={46} width={8} height={6} fill="none" stroke="#33241f" strokeWidth={2} />
      </svg>
      <Suspense fallback={<p className="flight-log__status">Loading flight log…</p>}>
        <FlightLog />
      </Suspense>
    </div>
  );
}
