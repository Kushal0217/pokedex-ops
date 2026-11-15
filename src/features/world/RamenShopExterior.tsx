import { PixelSpriteGroup } from './PixelSprite';
import { kushalSprite } from './kushalSprite';

/**
 * Ramen-shop exterior with Kushal's sprite standing outside.
 *
 * Original illustrated scenery (flat shapes, ink outline, light from the upper
 * left) with pixel-scale details. Every colour is a theme token, and the
 * lantern / window / doorway light layers fade in through `--glow`, so day,
 * evening and night share exactly this artwork.
 *
 * Purely decorative: labels and controls are real HTML layered over it.
 */
const VIEW_W = 480;
const VIEW_H = 340;
/** Size of one sprite pixel in scene units; the shared sprite scale for the town. */
export const SPRITE_PX = 2.5;

const INK = { stroke: 'var(--outline)', strokeWidth: 3, strokeLinejoin: 'round' as const };
const THIN = { stroke: 'var(--outline)', strokeWidth: 2, strokeLinejoin: 'round' as const };

/** A stepped (banded) pool of light: pixel-style, no gradients. */
function LightPool({ cx, cy, rx, ry }: { cx: number; cy: number; rx: number; ry: number }) {
  return (
    <g fill="var(--light)" style={{ opacity: 'var(--glow)' }}>
      <ellipse cx={cx} cy={cy} rx={rx} ry={ry} opacity={0.14} />
      <ellipse cx={cx} cy={cy} rx={rx * 0.72} ry={ry * 0.72} opacity={0.16} />
      <ellipse cx={cx} cy={cy} rx={rx * 0.44} ry={ry * 0.44} opacity={0.2} />
    </g>
  );
}

function Tree({ x, y, s = 1 }: { x: number; y: number; s?: number }) {
  return (
    <g transform={`translate(${x} ${y}) scale(${s})`}>
      <ellipse cx={6} cy={50} rx={26} ry={7} fill="var(--cast-shadow)" opacity="var(--cast-shadow-o)" />
      <rect x={-5} y={24} width={10} height={24} fill="var(--trunk)" {...THIN} />
      <circle cx={0} cy={0} r={30} fill="var(--tree)" {...INK} />
      <circle cx={-9} cy={-10} r={14} fill="var(--tree-hi)" />
      <path d="M 6 26 A 30 30 0 0 0 28 8 A 34 34 0 0 1 6 26 Z" fill="var(--tree-lo)" />
      <rect x={10} y={4} width={4} height={4} fill="var(--tree-lo)" />
      <rect x={-18} y={10} width={4} height={4} fill="var(--tree-lo)" />
      <rect x={-2} y={-18} width={4} height={4} fill="var(--tree-hi)" />
    </g>
  );
}

function Bush({ x, y }: { x: number; y: number }) {
  return (
    <g transform={`translate(${x} ${y})`}>
      <path d="M -22 8 A 12 12 0 0 1 -8 -6 A 13 13 0 0 1 12 -6 A 11 11 0 0 1 22 8 Z" fill="var(--tree)" {...THIN} />
      <rect x={-10} y={-4} width={4} height={4} fill="var(--tree-hi)" />
      <rect x={2} y={-6} width={4} height={4} fill="var(--tree-hi)" />
      <rect x={10} y={0} width={4} height={4} fill="var(--tree-lo)" />
    </g>
  );
}

function Lantern({ x, y }: { x: number; y: number }) {
  return (
    <g transform={`translate(${x} ${y})`}>
      <g fill="var(--light)" style={{ opacity: 'var(--glow)' }}>
        <circle cx={0} cy={15} r={24} opacity={0.16} />
        <circle cx={0} cy={15} r={16} opacity={0.22} />
      </g>
      <rect x={-1} y={-8} width={2} height={8} fill="var(--outline)" />
      <rect x={-7} y={0} width={14} height={30} rx={7} fill="var(--lantern)" {...THIN} />
      <rect x={-7} y={18} width={14} height={8} fill="var(--lantern-lo)" opacity={0.6} />
      <rect x={-3} y={6} width={3} height={12} fill="var(--light)" style={{ opacity: 'calc(0.25 + var(--glow) * 0.6)' }} />
      <rect x={-5} y={-1} width={10} height={4} fill="var(--lantern-band)" />
      <rect x={-5} y={27} width={10} height={4} fill="var(--lantern-band)" />
    </g>
  );
}

function ShopWindow({ x }: { x: number }) {
  return (
    <g transform={`translate(${x} 172)`}>
      <rect x={0} y={0} width={36} height={44} fill="var(--window)" {...THIN} />
      <path d="M 4 22 L 18 4 L 26 4 L 4 32 Z" fill="var(--window-glint)" opacity={0.7} />
      <rect x={17} y={0} width={2} height={44} fill="var(--wood-lo)" />
      <rect x={0} y={21} width={36} height={2} fill="var(--wood-lo)" />
      <rect x={-4} y={44} width={44} height={6} fill="var(--wood)" {...THIN} />
    </g>
  );
}

/** Grass tufts and pebbles: the small pixel details scattered over illustrated ground. */
const TUFTS: ReadonlyArray<readonly [number, number, 'hi' | 'lo']> = [
  [28, 150, 'hi'], [60, 210, 'lo'], [22, 268, 'hi'], [92, 300, 'lo'], [70, 120, 'lo'],
  [404, 150, 'hi'], [446, 206, 'lo'], [420, 262, 'hi'], [384, 306, 'lo'], [456, 310, 'hi'],
  [120, 250, 'hi'], [360, 240, 'lo'], [150, 318, 'lo'], [330, 322, 'hi'], [36, 326, 'lo'],
];

export function RamenShopExterior({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox={`0 0 ${VIEW_W} ${VIEW_H}`} aria-hidden="true" focusable="false">
      {/* ---- ground ---- */}
      <rect width={VIEW_W} height={VIEW_H} fill="var(--grass)" />
      <path d="M 0 96 Q 120 70 240 88 T 480 80 L 480 0 L 0 0 Z" fill="var(--grass-lo)" />
      <g shapeRendering="crispEdges">
        {TUFTS.map(([x, y, tone]) => (
          <g key={`${x}-${y}`} fill={tone === 'hi' ? 'var(--grass-hi)' : 'var(--grass-lo)'}>
            <rect x={x} y={y} width={3} height={6} />
            <rect x={x + 5} y={y - 3} width={3} height={9} />
            <rect x={x + 10} y={y + 1} width={3} height={5} />
          </g>
        ))}
      </g>

      {/* ---- back trees ---- */}
      <Tree x={74} y={66} s={1.05} />
      <Tree x={410} y={58} s={1.15} />
      <Tree x={18} y={170} s={0.8} />
      <Tree x={462} y={176} s={0.85} />

      {/* ---- forecourt and path ---- */}
      <path
        d="M 120 252 H 360 Q 372 252 372 264 V 284 Q 372 296 360 296 H 296 L 312 340 H 168 L 184 296 H 120 Q 108 296 108 284 V 264 Q 108 252 120 252 Z"
        fill="var(--path)"
        {...INK}
      />
      <g fill="var(--path-lo)" shapeRendering="crispEdges">
        <rect x={132} y={270} width={10} height={4} />
        <rect x={150} y={284} width={6} height={4} />
        <rect x={334} y={268} width={10} height={4} />
        <rect x={318} y={282} width={6} height={4} />
        <rect x={200} y={318} width={10} height={4} />
        <rect x={268} y={326} width={8} height={4} />
        <rect x={226} y={300} width={6} height={4} />
      </g>

      {/* ---- building cast shadow (light from upper left) ---- */}
      <path d="M 350 250 L 382 262 L 382 150 L 350 130 Z" fill="var(--cast-shadow)" opacity="var(--cast-shadow-o)" />

      {/* ---- walls ---- */}
      <rect x={130} y={128} width={220} height={124} fill="var(--wall)" {...INK} />
      <rect x={130} y={128} width={220} height={22} fill="var(--wall-lo)" />
      <rect x={130} y={238} width={220} height={14} fill="var(--stone)" {...THIN} />
      {/* timber frame */}
      <rect x={130} y={128} width={10} height={124} fill="var(--wood)" {...THIN} />
      <rect x={340} y={128} width={10} height={124} fill="var(--wood)" {...THIN} />
      <rect x={182} y={150} width={8} height={102} fill="var(--wood)" {...THIN} />
      <rect x={290} y={150} width={8} height={102} fill="var(--wood)" {...THIN} />

      {/* ---- windows ---- */}
      <ShopWindow x={143} />
      <ShopWindow x={301} />

      {/* ---- doorway and interior ---- */}
      <rect x={190} y={150} width={100} height={102} fill="var(--interior)" {...INK} />
      <g fill="var(--interior-detail)" shapeRendering="crispEdges">
        {/* counter and stools glimpsed inside */}
        <rect x={192} y={206} width={96} height={6} />
        <rect x={202} y={218} width={12} height={4} />
        <rect x={206} y={222} width={4} height={28} />
        <rect x={266} y={218} width={12} height={4} />
        <rect x={270} y={222} width={4} height={28} />
        <rect x={234} y={218} width={12} height={4} />
        <rect x={238} y={222} width={4} height={28} />
      </g>
      {/* noren curtain */}
      {[0, 1, 2, 3].map((i) => (
        <g key={i} transform={`translate(${192 + i * 24} 150)`}>
          <rect x={0} y={0} width={24} height={i % 2 === 0 ? 38 : 34} fill="var(--noren)" {...THIN} />
          <rect x={16} y={2} width={6} height={i % 2 === 0 ? 34 : 30} fill="var(--noren-lo)" />
          <circle cx={11} cy={17} r={5} fill="none" stroke="var(--noren-mark)" strokeWidth={2.5} />
        </g>
      ))}
      <rect x={186} y={146} width={108} height={7} fill="var(--wood-lo)" {...THIN} />

      {/* ---- roof ---- */}
      <path d="M 108 136 L 136 66 H 344 L 372 136 Z" fill="var(--roof)" {...INK} />
      <path d="M 136 66 H 344 L 349 78 H 131 Z" fill="var(--roof-hi)" />
      <g stroke="var(--roof-lo)" strokeWidth={3}>
        <path d="M 126 92 H 354" />
        <path d="M 119 110 H 361" />
      </g>
      <g fill="var(--roof-lo)" shapeRendering="crispEdges">
        {[150, 190, 290, 330].map((x) => (
          <rect key={x} x={x} y={80} width={4} height={10} />
        ))}
        {[142, 170, 310, 338].map((x) => (
          <rect key={x} x={x} y={96} width={4} height={12} />
        ))}
        {[134, 164, 316, 346].map((x) => (
          <rect key={x} x={x} y={114} width={4} height={14} />
        ))}
      </g>
      <rect x={104} y={128} width={272} height={12} rx={3} fill="var(--roof-lo)" {...INK} />
      <rect x={130} y={58} width={220} height={12} rx={3} fill="var(--wood-lo)" {...INK} />

      {/* ---- shop sign: an original bowl mark, no lettering baked into art ---- */}
      <g transform="translate(240 100)">
        <g fill="var(--light)" style={{ opacity: 'var(--glow)' }}>
          <rect x={-58} y={-34} width={116} height={64} rx={10} opacity={0.18} />
        </g>
        <rect x={-48} y={-26} width={96} height={48} rx={4} fill="var(--wood)" {...INK} />
        <rect x={-41} y={-19} width={82} height={34} fill="var(--noren-mark)" {...THIN} />
        <g shapeRendering="crispEdges">
          <rect x={-10} y={-15} width={3} height={7} fill="var(--wood-lo)" opacity={0.6} />
          <rect x={-1} y={-17} width={3} height={8} fill="var(--wood-lo)" opacity={0.6} />
          <rect x={8} y={-15} width={3} height={7} fill="var(--wood-lo)" opacity={0.6} />
          <rect x={-21} y={-6} width={42} height={5} fill="var(--lantern)" />
          <rect x={-18} y={-1} width={36} height={5} fill="var(--lantern)" />
          <rect x={-14} y={4} width={28} height={4} fill="var(--lantern-lo)" />
          <rect x={-8} y={8} width={16} height={3} fill="var(--lantern-lo)" />
          <rect x={-21} y={-6} width={42} height={2} fill="var(--outline)" opacity={0.35} />
        </g>
        <path d="M 12 -12 L 30 -18 M 14 -9 L 32 -13" stroke="var(--wood-lo)" strokeWidth={2.5} strokeLinecap="round" />
      </g>

      {/* ---- lanterns ---- */}
      <Lantern x={158} y={146} />
      <Lantern x={322} y={146} />

      {/* ---- light spilling from the doorway ---- */}
      <LightPool cx={240} cy={270} rx={112} ry={34} />

      {/* ---- props ---- */}
      <Bush x={118} y={246} />
      <Bush x={366} y={246} />
      {/* A-frame menu stand */}
      <g transform="translate(318 244)">
        <ellipse cx={4} cy={38} rx={16} ry={4} fill="var(--cast-shadow)" opacity="var(--cast-shadow-o)" />
        <path d="M -12 38 L -8 0 H 8 L 12 38" fill="none" stroke="var(--wood-lo)" strokeWidth={4} strokeLinejoin="round" />
        <rect x={-11} y={2} width={22} height={28} fill="var(--noren-mark)" {...THIN} />
        <g fill="var(--wood-lo)" shapeRendering="crispEdges">
          <rect x={-7} y={8} width={14} height={2} />
          <rect x={-7} y={14} width={10} height={2} />
          <rect x={-7} y={20} width={12} height={2} />
        </g>
        <rect x={-7} y={25} width={5} height={2} fill="var(--lantern)" />
      </g>

      {/* ---- Kushal ---- */}
      <ellipse cx={226} cy={317} rx={19} ry={5} fill="var(--cast-shadow)" opacity="var(--cast-shadow-o)" />
      <PixelSpriteGroup sprite={kushalSprite} x={206} y={248} px={SPRITE_PX} />
    </svg>
  );
}
