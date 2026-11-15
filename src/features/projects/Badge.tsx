/**
 * Project badges: one original family. Every badge is a faceted enamel pin
 * with the same ink rim, highlight and shadow; shape, accent colour and the
 * pixel emblem vary per project. Decorative: the project name is always shown
 * as real text beside or below it.
 */
interface BadgeDesign {
  shape: 'hex' | 'shield' | 'round';
  accent: string;
  accentDark: string;
  emblem: (readonly [number, number, number, number, string])[];
}

const INK = '#2e211c';
const CREAM = '#fbf2dc';

const SHAPES: Record<BadgeDesign['shape'], string> = {
  hex: 'M 32 4 L 56 18 V 46 L 32 60 L 8 46 V 18 Z',
  shield: 'M 10 8 H 54 V 34 Q 54 52 32 60 Q 10 52 10 34 Z',
  round: 'M 32 5 A 27 27 0 1 1 31.9 5 Z',
};

/** Emblem pixels: [x, y, w, h, fill] on the 64-unit badge. */
const DESIGNS: Record<string, BadgeDesign> = {
  // Database cylinder with a wrench: a tool for databases.
  'pokedex-ops': {
    shape: 'hex',
    accent: '#1f8a8a',
    accentDark: '#14636a',
    emblem: [
      // three stacked discs
      [16, 15, 22, 2, CREAM], [14, 17, 26, 6, CREAM],
      [14, 26, 26, 6, CREAM],
      [14, 35, 26, 6, CREAM], [16, 41, 22, 2, CREAM],
      [17, 19, 4, 2, '#1f8a8a'], [17, 28, 4, 2, '#e24a38'], [17, 37, 4, 2, '#e0a34a'],
      [24, 19, 12, 2, '#d9c9a3'], [24, 28, 12, 2, '#d9c9a3'], [24, 37, 12, 2, '#d9c9a3'],
      // wrench laid across the corner
      [37, 31, 6, 6, INK], [41, 35, 6, 6, INK], [45, 39, 6, 6, INK], [49, 43, 6, 6, INK],
      [33, 25, 12, 10, INK],
      [38, 32, 4, 4, '#ffd978'], [42, 36, 4, 4, '#ffd978'], [46, 40, 4, 4, '#ffd978'], [50, 44, 4, 4, '#ffd978'],
      [34, 26, 10, 8, '#ffd978'], [37, 26, 4, 4, INK],
    ],
  },
};

/** Used until a project has its own design. */
const DEFAULT_DESIGN: BadgeDesign = {
  shape: 'round',
  accent: '#8a6d4a',
  accentDark: '#6b5238',
  emblem: [
    [29, 20, 6, 24, CREAM], [20, 29, 24, 6, CREAM], [24, 24, 4, 4, CREAM], [36, 24, 4, 4, CREAM], [24, 36, 4, 4, CREAM], [36, 36, 4, 4, CREAM],
  ],
};

export function Badge({ design, className }: { design?: string; className?: string }) {
  const d = (design && DESIGNS[design]) || DEFAULT_DESIGN;
  const shape = SHAPES[d.shape];
  return (
    <svg className={className} viewBox="0 0 68 70" aria-hidden="true" focusable="false">
      <path d={shape} transform="translate(5 6)" fill={INK} opacity={0.3} />
      <path d={shape} transform="translate(2 2)" fill={d.accent} stroke={INK} strokeWidth={3.5} strokeLinejoin="round" />
      <g transform="translate(2 2)">
        <path d={shape} fill={d.accentDark} transform="translate(32 32) scale(0.84) translate(-32 -32)" opacity={0.55} />
        <path d="M 14 22 L 30 10 L 36 13 L 16 28 Z" fill={CREAM} opacity={0.35} />
        <g shapeRendering="crispEdges">
          {d.emblem.map(([x, y, w, h, fill], i) => (
            <rect key={i} x={x} y={y} width={w} height={h} fill={fill} />
          ))}
        </g>
      </g>
    </svg>
  );
}

/** Small badge-case icon for the persistent button. */
export function BadgeCaseIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 20 16" aria-hidden="true" focusable="false" shapeRendering="crispEdges">
      <rect x="6" y="0" width="8" height="2" fill="currentColor" />
      <rect x="6" y="0" width="2" height="4" fill="currentColor" />
      <rect x="12" y="0" width="2" height="4" fill="currentColor" />
      <rect x="0" y="3" width="20" height="13" fill="currentColor" />
      <rect x="2" y="5" width="16" height="9" fill="var(--badge-icon-inner, #fbf2dc)" />
      <rect x="4" y="7" width="3" height="3" fill="#1f8a8a" />
      <rect x="9" y="7" width="3" height="3" fill="#c6452f" />
      <rect x="14" y="7" width="2" height="3" fill="#e0a34a" />
      <rect x="4" y="11" width="12" height="1" fill="currentColor" opacity="0.5" />
    </svg>
  );
}
