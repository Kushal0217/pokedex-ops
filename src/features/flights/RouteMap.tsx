import { useMemo } from 'react';
import type { Route } from './flightStats';
import type { FlightData } from './types';
import { WORLD_LAND_PATH } from './worldMap.generated';

/** Equirectangular: x = lon + 180, y = 90 - lat. Flat map; no globe, no map service. */
const project = (lat: number, lon: number) => ({ x: lon + 180, y: 90 - lat });

/** A view box around the airports in use, padded, at a fixed 2:1 shape, kept inside the world. */
function viewFor(points: { x: number; y: number }[]) {
  const WORLD = { w: 360, h: 150 };
  if (points.length === 0) return { x: 0, y: 0, w: WORLD.w, h: WORLD.h };
  const xs = points.map((p) => p.x);
  const ys = points.map((p) => p.y);
  let w = Math.max(Math.max(...xs) - Math.min(...xs) + 30, 70);
  let h = Math.max(Math.max(...ys) - Math.min(...ys) + 24, 35);
  if (w < h * 2) w = h * 2;
  else h = w / 2;
  w = Math.min(w, WORLD.w);
  h = Math.min(h, WORLD.h);
  const cx = (Math.max(...xs) + Math.min(...xs)) / 2;
  const cy = (Math.max(...ys) + Math.min(...ys)) / 2;
  return { x: Math.min(Math.max(cx - w / 2, 0), WORLD.w - w), y: Math.min(Math.max(cy - h / 2, 0), WORLD.h - h), w, h };
}

interface Props {
  data: FlightData;
  routes: Route[];
  selectedKey: string | null;
  onSelect: (key: string) => void;
}

/**
 * Flat route map: airport markers and curved connections. A pointer
 * convenience only: every route is also a real button below the map, and
 * every flight is in the All flights tab.
 */
export function RouteMap({ data, routes, selectedKey, onSelect }: Props) {
  const drawn = routes.filter((r) => r.onMap);
  const codes = useMemo(() => [...new Set(drawn.flatMap((r) => [r.a, r.b]))], [drawn]);
  const at = (code: string) => project(data.airports[code]!.lat, data.airports[code]!.lon);
  const view = viewFor(codes.map(at));
  const unit = view.w / 300; // keeps strokes and markers the same size on screen at any zoom

  const arc = (route: Route) => {
    const p = at(route.a);
    const q = at(route.b);
    const bulge = Math.hypot(q.x - p.x, q.y - p.y) * 0.2;
    return `M ${p.x} ${p.y} Q ${(p.x + q.x) / 2} ${(p.y + q.y) / 2 - bulge} ${q.x} ${q.y}`;
  };

  return (
    <svg className="route-map" viewBox={`${view.x} ${view.y} ${view.w} ${view.h}`} aria-hidden="true" focusable="false">
      <rect x={0} y={0} width={360} height={180} fill="#16203a" />
      <path d={WORLD_LAND_PATH} fill="#31466b" stroke="#4a6592" strokeWidth={unit * 0.6} strokeLinejoin="round" />
      {drawn.map((route) => {
        const selected = route.key === selectedKey;
        return (
          <g key={route.key} onClick={() => onSelect(route.key)} style={{ cursor: 'pointer' }}>
            <path d={arc(route)} fill="none" stroke="transparent" strokeWidth={unit * 12} />
            <path
              d={arc(route)}
              fill="none"
              stroke={selected ? '#ffd978' : '#f08a5c'}
              strokeWidth={unit * (selected ? 3.2 : 1.8)}
              strokeLinecap="round"
              strokeDasharray={selected ? undefined : `${unit * 5} ${unit * 3}`}
            />
          </g>
        );
      })}
      {codes.map((code) => {
        const p = at(code);
        return (
          <g key={code}>
            <circle cx={p.x} cy={p.y} r={unit * 3.4} fill="#16203a" />
            <circle cx={p.x} cy={p.y} r={unit * 2.4} fill="#fbf2dc" />
            <text
              x={p.x + (p.x > view.x + view.w * 0.85 ? -unit * 5 : unit * 5)}
              y={p.y - unit * 4}
              textAnchor={p.x > view.x + view.w * 0.85 ? 'end' : 'start'}
              fontSize={unit * 9} fontWeight={700}
              fill="#fbf2dc"
              stroke="#16203a"
              strokeWidth={unit * 2.4}
              paintOrder="stroke"
            >
              {code}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
