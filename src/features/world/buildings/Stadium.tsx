import { INK, LightPool, THIN } from './scenery';

function Floodlight({ x, y }: { x: number; y: number }) {
  return (
    <g transform={`translate(${x} ${y})`}>
      <g fill="var(--light)" style={{ opacity: 'var(--glow)' }}>
        <circle cx={0} cy={-52} r={30} opacity={0.14} />
        <circle cx={0} cy={-52} r={18} opacity={0.22} />
      </g>
      <rect x={-3} y={-46} width={6} height={46} fill="var(--metal-lo)" {...THIN} />
      <rect x={-15} y={-62} width={30} height={18} rx={2} fill="var(--metal)" {...THIN} />
      <g shapeRendering="crispEdges" fill="var(--light)" style={{ opacity: 'calc(0.45 + var(--glow) * 0.55)' }}>
        {[-11, -3, 5].map((lx) => [-58, -51].map((ly) => <rect key={`${lx}${ly}`} x={lx} y={ly} width={6} height={5} />))}
      </g>
    </g>
  );
}

/**
 * Stadium: an oval bowl with blue-and-garnet seating, floodlights and an
 * arched gate. No club crest is used. Local origin (0, 0) is the bottom centre
 * of the gate.
 */
export function Stadium() {
  const seats = Array.from({ length: 18 }, (_, i) => i);
  return (
    <g>
      <path d="M 150 -4 L 178 8 L 178 -96 L 150 -112 Z" fill="var(--cast-shadow)" opacity="var(--cast-shadow-o)" />
      <Floodlight x={-132} y={-150} />
      <Floodlight x={132} y={-150} />
      {/* outer bowl wall */}
      <path d="M -152 -124 V -22 Q -152 0 -130 0 H 130 Q 152 0 152 -22 V -124 Z" fill="var(--wall)" {...INK} />
      <rect x={-152} y={-18} width={304} height={18} fill="var(--stone)" opacity={0.9} />
      <g fill="var(--wall-lo)" shapeRendering="crispEdges">
        {[-126, -98, -70, -42, 42, 70, 98, 126].map((x) => <rect key={x} x={x - 4} y={-104} width={8} height={88} />)}
      </g>
      <g fill="var(--window)" stroke="var(--outline)" strokeWidth={2}>
        {[-112, -84, -56, 56, 84, 112].map((x) => <rect key={x} x={x - 7} y={-70} width={14} height={22} rx={7} />)}
      </g>
      {/* stands (seen from above the rim) and pitch */}
      <ellipse cx={0} cy={-124} rx={152} ry={50} fill="var(--stone)" {...INK} />
      <g>
        {seats.map((i) => {
          const a0 = (i / seats.length) * Math.PI * 2;
          const a1 = ((i + 1) / seats.length) * Math.PI * 2;
          const p = (a: number, rx: number, ry: number) => `${(Math.cos(a) * rx).toFixed(1)} ${(-124 + Math.sin(a) * ry).toFixed(1)}`;
          return (
            <path
              key={i}
              d={`M ${p(a0, 142, 43)} A 142 43 0 0 1 ${p(a1, 142, 43)} L ${p(a1, 104, 27)} A 104 27 0 0 0 ${p(a0, 104, 27)} Z`}
              fill={i % 2 === 0 ? 'var(--seat-a)' : 'var(--seat-b)'}
            />
          );
        })}
      </g>
      <ellipse cx={0} cy={-124} rx={104} ry={27} fill="var(--pitch)" {...THIN} />
      <g stroke="var(--noren-mark)" strokeWidth={1.5} fill="none" opacity={0.85}>
        <path d="M 0 -150 V -98" />
        <ellipse cx={0} cy={-124} rx={16} ry={6} />
        <path d="M -98 -132 H -80 V -116 H -98" />
        <path d="M 98 -132 H 80 V -116 H 98" />
      </g>
      <g fill="var(--pitch-lo)" shapeRendering="crispEdges">
        <rect x={-60} y={-140} width={20} height={32} opacity={0.6} />
        <rect x={-20} y={-148} width={20} height={48} opacity={0.6} />
        <rect x={20} y={-148} width={20} height={48} opacity={0.6} />
        <rect x={60} y={-138} width={16} height={28} opacity={0.6} />
      </g>
      <ellipse cx={0} cy={-124} rx={152} ry={50} fill="none" {...INK} />
      {/* front floodlights */}
      <Floodlight x={-150} y={-70} />
      <Floodlight x={150} y={-70} />
      {/* gate */}
      <path d="M -30 0 V -44 A 30 30 0 0 1 30 -44 V 0 Z" fill="var(--interior)" {...INK} />
      <path d="M -18 0 V -40 A 18 18 0 0 1 18 -40 V 0 Z" fill="var(--interior-detail)" opacity={0.7} />
      {/* striped banners */}
      {[-58, 46].map((x) => (
        <g key={x} transform={`translate(${x} -64)`}>
          <rect x={0} y={0} width={12} height={38} fill="var(--seat-a)" {...THIN} />
          <rect x={4} y={1} width={4} height={36} fill="var(--seat-b)" />
        </g>
      ))}
      {/* sign: an original goal-and-ball mark */}
      <g transform="translate(0 -92)">
        <g fill="var(--light)" style={{ opacity: 'var(--glow)' }}>
          <rect x={-40} y={-20} width={80} height={36} rx={8} opacity={0.18} />
        </g>
        <rect x={-32} y={-14} width={64} height={26} rx={4} fill="var(--wood)" {...INK} />
        <rect x={-27} y={-9} width={54} height={16} fill="var(--noren-mark)" {...THIN} />
        <g shapeRendering="crispEdges">
          <rect x={-18} y={-6} width={2} height={11} fill="var(--outline)" />
          <rect x={4} y={-6} width={2} height={11} fill="var(--outline)" />
          <rect x={-18} y={-6} width={24} height={2} fill="var(--outline)" />
          <rect x={-13} y={-2} width={2} height={7} fill="var(--wood-lo)" opacity={0.5} />
          <rect x={-7} y={-2} width={2} height={7} fill="var(--wood-lo)" opacity={0.5} />
          <rect x={-1} y={-2} width={2} height={7} fill="var(--wood-lo)" opacity={0.5} />
          <rect x={13} y={0} width={6} height={6} fill="var(--outline)" />
          <rect x={15} y={2} width={2} height={2} fill="var(--noren-mark)" />
        </g>
      </g>
      <LightPool cx={0} cy={14} rx={80} ry={24} />
    </g>
  );
}
