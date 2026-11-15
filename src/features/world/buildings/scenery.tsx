/** Shared scenery pieces and drawing constants for the town. Every colour is a theme token. */
export const INK = { stroke: 'var(--outline)', strokeWidth: 3, strokeLinejoin: 'round' as const };
export const THIN = { stroke: 'var(--outline)', strokeWidth: 2, strokeLinejoin: 'round' as const };

/** A stepped (banded) pool of light: pixel-style, no gradients. */
export function LightPool({ cx, cy, rx, ry }: { cx: number; cy: number; rx: number; ry: number }) {
  return (
    <g fill="var(--light)" style={{ opacity: 'var(--glow)' }}>
      <ellipse cx={cx} cy={cy} rx={rx} ry={ry} opacity={0.14} />
      <ellipse cx={cx} cy={cy} rx={rx * 0.72} ry={ry * 0.72} opacity={0.16} />
      <ellipse cx={cx} cy={cy} rx={rx * 0.44} ry={ry * 0.44} opacity={0.2} />
    </g>
  );
}

/** Canopy lobes: [cx, cy, r]. Drawn twice (outlined, then filled) so the lobes share one outline. */
const CANOPY: ReadonlyArray<readonly [number, number, number]> = [
  [0, 2, 24], [-17, 6, 15], [17, 7, 15], [-10, -13, 16], [11, -12, 15], [0, -22, 12], [-2, 16, 16],
];
/** Leaf clusters: [x, y, tone]. Each is a small pixel sprig. */
const LEAVES: ReadonlyArray<readonly [number, number, 'hi' | 'lo']> = [
  [-22, -6, 'hi'], [-12, -24, 'hi'], [-4, -14, 'hi'], [-24, 8, 'hi'], [-10, 2, 'hi'], [2, -28, 'hi'], [8, -8, 'hi'],
  [14, -18, 'lo'], [4, 6, 'lo'], [18, -2, 'lo'], [-14, 16, 'lo'], [10, 18, 'lo'], [22, 10, 'lo'], [-2, 24, 'lo'],
];

export function Tree({ x, y, s = 1 }: { x: number; y: number; s?: number }) {
  return (
    <g transform={`translate(${x} ${y}) scale(${s})`}>
      <ellipse cx={7} cy={52} rx={28} ry={7} fill="var(--cast-shadow)" opacity="var(--cast-shadow-o)" />
      {/* trunk with root flare, a branch fork and bark */}
      <path d="M -6 22 V 44 L -11 51 H 11 L 6 44 V 22 Z" fill="var(--trunk)" {...THIN} />
      <path d="M 0 30 L 9 20" stroke="var(--outline)" strokeWidth={6} strokeLinecap="round" />
      <path d="M 0 30 L 9 20" stroke="var(--trunk)" strokeWidth={3} strokeLinecap="round" />
      <g fill="var(--outline)" opacity={0.4} shapeRendering="crispEdges">
        <rect x={-3} y={32} width={2} height={7} />
        <rect x={2} y={38} width={2} height={6} />
        <rect x={-2} y={44} width={2} height={4} />
      </g>
      <rect x={3} y={24} width={3} height={22} fill="var(--outline)" opacity={0.2} />
      {/* canopy */}
      <g fill="var(--tree)" {...INK}>
        {CANOPY.map(([cx, cy, r]) => <circle key={`${cx}-${cy}`} cx={cx} cy={cy} r={r} />)}
      </g>
      <g fill="var(--tree)">
        {CANOPY.map(([cx, cy, r]) => <circle key={`${cx}-${cy}`} cx={cx} cy={cy} r={r} />)}
      </g>
      {/* shade on the side away from the light, and under each upper lobe */}
      <path d="M 30 2 A 15 15 0 0 1 20 21 A 16 16 0 0 1 -8 31 A 34 30 0 0 0 30 2 Z" fill="var(--tree-lo)" />
      <path d="M -24 -4 A 16 16 0 0 0 0 -2 A 15 15 0 0 0 24 -4 A 30 12 0 0 1 -24 -4 Z" fill="var(--tree-lo)" opacity={0.55} />
      {/* lit clumps */}
      <circle cx={-12} cy={-16} r={9} fill="var(--tree-hi)" />
      <circle cx={-1} cy={-24} r={6} fill="var(--tree-hi)" />
      <circle cx={-20} cy={3} r={6} fill="var(--tree-hi)" opacity={0.8} />
      <circle cx={9} cy={-14} r={5} fill="var(--tree-hi)" opacity={0.7} />
      {/* pixel leaf sprigs */}
      <g shapeRendering="crispEdges">
        {LEAVES.map(([lx, ly, tone]) => (
          <g key={`${lx}-${ly}`} fill={tone === 'hi' ? 'var(--tree-hi)' : 'var(--tree-lo)'}>
            <rect x={lx} y={ly} width={4} height={2} />
            <rect x={lx + 2} y={ly + 2} width={4} height={2} />
            <rect x={lx - 2} y={ly + 4} width={2} height={2} />
          </g>
        ))}
        {/* a few fruit */}
        {([[-6, 8], [14, 2], [4, -18], [-18, -10]] as const).map(([fx, fy]) => (
          <g key={`${fx}-${fy}`}>
            <rect x={fx} y={fy} width={4} height={4} fill="var(--lantern)" />
            <rect x={fx} y={fy} width={2} height={2} fill="var(--light)" />
          </g>
        ))}
      </g>
    </g>
  );
}

export function Bush({ x, y }: { x: number; y: number }) {
  const lobes: ReadonlyArray<readonly [number, number, number]> = [[-14, 2, 9], [-3, -5, 11], [10, -2, 10], [19, 4, 6], [-21, 5, 5]];
  return (
    <g transform={`translate(${x} ${y})`}>
      <ellipse cx={3} cy={9} rx={27} ry={4} fill="var(--cast-shadow)" opacity="var(--cast-shadow-o)" />
      <g fill="var(--tree)" {...THIN}>
        {lobes.map(([cx, cy, r]) => <circle key={cx} cx={cx} cy={cy} r={r} />)}
        <rect x={-24} y={2} width={48} height={7} rx={3} />
      </g>
      <g fill="var(--tree)">
        {lobes.map(([cx, cy, r]) => <circle key={cx} cx={cx} cy={cy} r={r} />)}
        <rect x={-23} y={3} width={46} height={5} />
      </g>
      <path d="M -22 8 H 23 V 3 A 30 8 0 0 1 -22 5 Z" fill="var(--tree-lo)" />
      <circle cx={-6} cy={-8} r={5} fill="var(--tree-hi)" />
      <circle cx={-16} cy={-1} r={3} fill="var(--tree-hi)" />
      <circle cx={8} cy={-6} r={3.5} fill="var(--tree-hi)" opacity={0.8} />
      <g shapeRendering="crispEdges">
        {([[-12, -4], [0, -12], [12, -8], [4, -2], [-18, 2], [16, 0]] as const).map(([lx, ly], i) => (
          <g key={`${lx}-${ly}`} fill={i % 2 === 0 ? 'var(--tree-hi)' : 'var(--tree-lo)'}>
            <rect x={lx} y={ly} width={3} height={2} />
            <rect x={lx + 2} y={ly + 2} width={3} height={2} />
          </g>
        ))}
      </g>
    </g>
  );
}
