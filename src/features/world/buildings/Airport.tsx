import { INK, LightPool, THIN } from './scenery';

/**
 * Airport: a low terminal with a glass front, curved roof and control tower.
 * Local origin (0, 0) is the bottom centre of the doors.
 */
export function Airport() {
  return (
    <g>
      <path d="M 150 -2 L 176 9 L 176 -72 L 150 -88 Z" fill="var(--cast-shadow)" opacity="var(--cast-shadow-o)" />
      {/* control tower */}
      <g transform="translate(104 -92)">
        <rect x={-13} y={-78} width={26} height={80} fill="var(--wall)" {...INK} />
        <rect x={5} y={-78} width={8} height={80} fill="var(--wall-lo)" />
        <g fill="var(--wall-lo)" shapeRendering="crispEdges">
          <rect x={-8} y={-60} width={8} height={2} />
          <rect x={-8} y={-40} width={8} height={2} />
          <rect x={-8} y={-20} width={8} height={2} />
        </g>
        <g fill="var(--light)" style={{ opacity: 'var(--glow)' }}>
          <rect x={-36} y={-112} width={72} height={40} rx={10} opacity={0.16} />
        </g>
        <path d="M -24 -78 L -30 -104 H 30 L 24 -78 Z" fill="var(--window)" {...INK} />
        <path d="M -20 -84 L -8 -100 H 0 L -14 -84 Z" fill="var(--window-glint)" opacity={0.6} />
        <rect x={-10} y={-104} width={2} height={26} fill="var(--outline)" />
        <rect x={8} y={-104} width={2} height={26} fill="var(--outline)" />
        <rect x={-34} y={-110} width={68} height={8} rx={3} fill="var(--roof2-lo)" {...INK} />
        <rect x={-28} y={-80} width={56} height={6} rx={2} fill="var(--metal-lo)" {...THIN} />
        <rect x={-1} y={-130} width={2} height={20} fill="var(--outline)" />
        <g fill="var(--beacon)" style={{ opacity: 'var(--glow)' }}>
          <circle cx={0} cy={-132} r={10} opacity={0.3} />
        </g>
        <rect x={-3} y={-135} width={6} height={6} fill="var(--beacon)" {...THIN} />
      </g>
      {/* terminal */}
      <rect x={-152} y={-92} width={304} height={92} fill="var(--wall)" {...INK} />
      <rect x={-152} y={-12} width={304} height={12} fill="var(--stone)" {...THIN} />
      <rect x={-138} y={-74} width={276} height={38} fill="var(--window)" {...THIN} />
      <path d="M -132 -40 L -104 -72 H -90 L -118 -40 Z M -40 -40 L -12 -72 H -4 L -32 -40 Z M 70 -40 L 98 -72 H 106 L 78 -40 Z" fill="var(--window-glint)" opacity={0.55} />
      <g fill="var(--metal-lo)" shapeRendering="crispEdges">
        {[-104, -70, -36, 36, 70, 104].map((x) => <rect key={x} x={x - 1} y={-74} width={3} height={38} />)}
      </g>
      {/* people-height details behind the glass */}
      <g fill="var(--interior-detail)" opacity={0.45} shapeRendering="crispEdges">
        <rect x={-126} y={-48} width={16} height={12} />
        <rect x={-92} y={-52} width={6} height={16} />
        <rect x={50} y={-48} width={14} height={12} />
        <rect x={118} y={-52} width={6} height={16} />
      </g>
      {/* doors */}
      <rect x={-28} y={-54} width={56} height={54} fill="var(--interior)" {...INK} />
      <rect x={-1} y={-54} width={2} height={54} fill="var(--outline)" />
      <rect x={-22} y={-48} width={16} height={30} fill="var(--window)" opacity={0.75} />
      <rect x={6} y={-48} width={16} height={30} fill="var(--window)" opacity={0.75} />
      <rect x={-36} y={-62} width={72} height={9} rx={2} fill="var(--roof2)" {...THIN} />
      {/* curved roof */}
      <path d="M -160 -90 Q 0 -138 160 -90 V -84 H -160 Z" fill="var(--roof2)" {...INK} />
      <path d="M -140 -95 Q 0 -134 140 -95 Q 0 -126 -140 -95 Z" fill="var(--roof2-hi)" />
      <g fill="var(--roof2-lo)" shapeRendering="crispEdges">
        {[-110, -66, -22, 22, 66, 110].map((x) => <rect key={x} x={x} y={-100 - (1 - (x / 150) ** 2) * 10} width={3} height={12} />)}
      </g>
      {/* sign: an original pixel plane mark */}
      <g transform="translate(-84 -112)">
        <g fill="var(--light)" style={{ opacity: 'var(--glow)' }}>
          <rect x={-36} y={-22} width={72} height={40} rx={8} opacity={0.18} />
        </g>
        <rect x={-28} y={-16} width={56} height={28} rx={4} fill="var(--wood)" {...INK} />
        <rect x={-23} y={-11} width={46} height={18} fill="var(--noren-mark)" {...THIN} />
        <g shapeRendering="crispEdges" fill="var(--noren)">
          <rect x={-16} y={-4} width={30} height={4} />
          <rect x={14} y={-3} width={3} height={2} />
          <rect x={-6} y={-9} width={5} height={5} />
          <rect x={-4} y={0} width={8} height={3} />
          <rect x={-2} y={3} width={5} height={2} />
          <rect x={-17} y={-8} width={4} height={4} />
        </g>
      </g>
      {/* windsock */}
      <g transform="translate(-140 -92)">
        <rect x={-1} y={-40} width={3} height={40} fill="var(--metal-lo)" {...THIN} />
        <path d="M 2 -40 L 26 -36 L 26 -30 L 2 -28 Z" fill="var(--lantern)" {...THIN} />
        <rect x={9} y={-38} width={5} height={9} fill="var(--noren-mark)" />
      </g>
      <LightPool cx={0} cy={14} rx={84} ry={24} />
      {/* luggage trolley */}
      <g transform="translate(58 4)" shapeRendering="crispEdges">
        <rect x={-12} y={-10} width={24} height={4} fill="var(--metal-lo)" stroke="var(--outline)" strokeWidth={2} />
        <rect x={-10} y={-24} width={12} height={14} fill="var(--seat-b)" stroke="var(--outline)" strokeWidth={2} />
        <rect x={2} y={-20} width={9} height={10} fill="var(--noren)" stroke="var(--outline)" strokeWidth={2} />
        <rect x={-10} y={-5} width={5} height={5} fill="var(--outline)" />
        <rect x={6} y={-5} width={5} height={5} fill="var(--outline)" />
      </g>
    </g>
  );
}
