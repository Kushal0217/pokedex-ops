import { memo } from 'react';
import { Airport } from './buildings/Airport';
import { ProfileStudio } from './buildings/ProfileStudio';
import { RamenShop } from './buildings/RamenShop';
import { Stadium } from './buildings/Stadium';
import { Tree } from './buildings/scenery';
import { places, type Layout, type PlaceId } from './places';
import type { TownMap } from './townMap';

const BUILDINGS: Record<PlaceId, () => React.JSX.Element> = {
  profile: ProfileStudio,
  ramen: RamenShop,
  stadium: Stadium,
  airport: Airport,
};

const ROAD_W = 44;

/** Deterministic scatter so the ground detail is the same on every visit. */
function scatter(layout: Layout, map: TownMap) {
  let seed = layout.id === 'town' ? 7 : 19;
  const random = () => {
    seed = (seed * 1664525 + 1013904223) >>> 0;
    return seed / 4294967296;
  };
  const nearRoad = (x: number, y: number) =>
    layout.roads.some((road) =>
      road.slice(1).some(([bx, by], i) => {
        const [ax, ay] = road[i]!;
        const t = Math.max(0, Math.min(1, ((x - ax) * (bx - ax) + (y - ay) * (by - ay)) / ((bx - ax) ** 2 + (by - ay) ** 2 || 1)));
        return Math.hypot(x - (ax + t * (bx - ax)), y - (ay + t * (by - ay))) < ROAD_W / 2 + 12;
      }),
    );
  const spots: { x: number; y: number; kind: 'hi' | 'lo' | 'flower' }[] = [];
  const wanted = Math.round((layout.width * layout.height) / 9000);
  for (let tries = 0; spots.length < wanted && tries < wanted * 12; tries += 1) {
    const x = 16 + random() * (layout.width - 40);
    const y = 16 + random() * (layout.height - 32);
    const pick = random();
    if (nearRoad(x, y) || !map.isWalkable({ x, y: Math.max(y, 84) }) || map.placeAt({ x, y }) !== null) continue;
    spots.push({ x: Math.round(x), y: Math.round(y), kind: pick < 0.18 ? 'flower' : pick < 0.6 ? 'hi' : 'lo' });
  }
  return spots;
}

/**
 * The town's scenery for one layout: ground, roads, trees and every place's
 * building. Purely decorative; labels and controls are real HTML layered above.
 * All colours are theme tokens, so the three lighting modes share this artwork.
 */
export const TownArt = memo(function TownArt({ layout, map }: { layout: Layout; map: TownMap }) {
  const roadPaths = layout.roads.map((road) => 'M ' + road.map(([x, y]) => `${x} ${y}`).join(' L '));
  const spots = scatter(layout, map);
  const { width, height } = layout;
  return (
    <svg className="scene__art" viewBox={`0 0 ${width} ${height}`} aria-hidden="true" focusable="false">
      <rect width={width} height={height} fill="var(--grass)" />
      {/* soft far-ground band and patches */}
      <path d={`M 0 58 Q ${width * 0.25} 34 ${width * 0.5} 52 T ${width} 44 V 0 H 0 Z`} fill="var(--grass-lo)" />
      <g fill="var(--grass-hi)" opacity={0.35}>
        {layout.roads.map((road, i) => {
          const [x, y] = road[0]!;
          return <ellipse key={i} cx={(x * 37 + i * 211) % width} cy={(y * 53 + i * 157) % height} rx={90} ry={34} />;
        })}
      </g>

      {/* ground detail */}
      <g shapeRendering="crispEdges">
        {spots.map(({ x, y, kind }) =>
          kind === 'flower' ? (
            <g key={`${x}-${y}`}>
              <rect x={x + 2} y={y + 4} width={2} height={6} fill="var(--grass-lo)" />
              <rect x={x} y={y} width={6} height={4} fill="var(--noren-mark)" />
              <rect x={x + 2} y={y - 2} width={2} height={8} fill="var(--noren-mark)" />
              <rect x={x + 2} y={y} width={2} height={4} fill="var(--light)" />
            </g>
          ) : (
            <g key={`${x}-${y}`} fill={kind === 'hi' ? 'var(--grass-hi)' : 'var(--grass-lo)'}>
              <rect x={x} y={y} width={3} height={6} />
              <rect x={x + 5} y={y - 3} width={3} height={9} />
              <rect x={x + 10} y={y + 1} width={3} height={5} />
            </g>
          ),
        )}
      </g>

      {/* roads: one outlined network */}
      <g fill="none" strokeLinecap="round" strokeLinejoin="round">
        {roadPaths.map((d) => <path key={d} d={d} stroke="var(--outline)" strokeWidth={ROAD_W + 6} />)}
        {roadPaths.map((d) => <path key={d} d={d} stroke="var(--path)" strokeWidth={ROAD_W} />)}
        {roadPaths.map((d) => <path key={d} d={d} stroke="var(--path-lo)" strokeWidth={4} strokeDasharray="10 34" opacity={0.7} />)}
      </g>

      {/* trees behind (north of) buildings first, then buildings top to bottom, so nearer things overlap farther ones */}
      {[...layout.trees.map((t) => ({ y: t.y + 50 * t.s, node: <Tree key={`t${t.x}-${t.y}`} x={t.x} y={t.y} s={t.s} /> })),
        ...places.map((place) => {
          const Building = BUILDINGS[place.id];
          const door = place.door[layout.id];
          return { y: door.y, node: <g key={place.id} transform={`translate(${door.x} ${door.y})`}><Building /></g> };
        })]
        .sort((a, b) => a.y - b.y)
        .map((item) => item.node)}
    </svg>
  );
});
