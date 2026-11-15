import { INK, LightPool, THIN } from './scenery';

function StudioWindow({ x }: { x: number }) {
  return (
    <g transform={`translate(${x} -78)`}>
      <rect x={0} y={0} width={40} height={38} fill="var(--window)" {...THIN} />
      {/* a monitor glimpsed through the glass */}
      <g shapeRendering="crispEdges">
        <rect x={8} y={10} width={24} height={17} fill="var(--screen)" />
        <rect x={11} y={13} width={10} height={2} fill="var(--screen-ink)" />
        <rect x={11} y={17} width={16} height={2} fill="var(--screen-ink)" opacity={0.7} />
        <rect x={11} y={21} width={7} height={2} fill="var(--screen-ink)" />
        <rect x={17} y={27} width={6} height={4} fill="var(--screen)" />
        <rect x={12} y={31} width={16} height={2} fill="var(--screen)" />
      </g>
      <path d="M 3 16 L 14 3 L 20 3 L 3 24 Z" fill="var(--window-glint)" opacity={0.55} />
      <rect x={-4} y={38} width={48} height={6} fill="var(--wood)" {...THIN} />
    </g>
  );
}

/**
 * Profile studio: Kushal's small work studio. Same perspective and ink as the
 * rest of the town. Local origin (0, 0) is the bottom centre of the door.
 */
export function ProfileStudio() {
  return (
    <g>
      <path d="M 92 0 L 118 10 L 118 -78 L 92 -96 Z" fill="var(--cast-shadow)" opacity="var(--cast-shadow-o)" />
      {/* chimney */}
      <rect x={48} y={-176} width={22} height={40} fill="var(--stone)" {...INK} />
      <rect x={44} y={-180} width={30} height={8} fill="var(--wall-lo)" {...THIN} />
      {/* walls */}
      <rect x={-92} y={-98} width={184} height={98} fill="var(--wall)" {...INK} />
      <rect x={-92} y={-98} width={184} height={18} fill="var(--wall-lo)" />
      <rect x={-92} y={-12} width={184} height={12} fill="var(--stone)" {...THIN} />
      <rect x={-92} y={-98} width={9} height={98} fill="var(--wood)" {...THIN} />
      <rect x={83} y={-98} width={9} height={98} fill="var(--wood)" {...THIN} />
      <g shapeRendering="crispEdges" fill="var(--wall-lo)">
        <rect x={-74} y={-24} width={8} height={2} />
        <rect x={62} y={-28} width={8} height={2} />
        <rect x={-30} y={-70} width={6} height={2} />
      </g>
      <StudioWindow x={-76} />
      <StudioWindow x={36} />
      {/* door */}
      <rect x={-20} y={-62} width={40} height={62} fill="var(--wood)" {...INK} />
      <rect x={-14} y={-56} width={28} height={20} fill="var(--window)" {...THIN} />
      <rect x={-14} y={-30} width={28} height={24} fill="var(--wood-lo)" opacity={0.5} />
      <rect x={10} y={-30} width={4} height={6} fill="var(--light)" {...THIN} />
      <rect x={-26} y={-2} width={52} height={6} fill="var(--stone)" {...THIN} />
      {/* door lamp */}
      <g transform="translate(0 -74)">
        <g fill="var(--light)" style={{ opacity: 'var(--glow)' }}>
          <circle r={22} opacity={0.16} />
          <circle r={13} opacity={0.24} />
        </g>
        <rect x={-6} y={-5} width={12} height={10} rx={3} fill="var(--light)" {...THIN} />
      </g>
      {/* roof */}
      <path d="M -110 -92 L -84 -152 H 84 L 110 -92 Z" fill="var(--roof2)" {...INK} />
      <path d="M -84 -152 H 84 L 89 -141 H -89 Z" fill="var(--roof2-hi)" />
      <g stroke="var(--roof2-lo)" strokeWidth={3}>
        <path d="M -95 -126 H 95" />
        <path d="M -102 -109 H 102" />
      </g>
      <g fill="var(--roof2-lo)" shapeRendering="crispEdges">
        {[-70, -30, 20, 60].map((x) => <rect key={x} x={x} y={-139} width={4} height={11} />)}
        {[-84, -48, 40, 76].map((x) => <rect key={x} x={x} y={-123} width={4} height={12} />)}
        {[-92, -58, 50, 86].map((x) => <rect key={x} x={x} y={-106} width={4} height={10} />)}
      </g>
      <rect x={-114} y={-98} width={228} height={11} rx={3} fill="var(--roof2-lo)" {...INK} />
      <rect x={-90} y={-160} width={180} height={11} rx={3} fill="var(--wood-lo)" {...INK} />
      {/* sign: an original pixel laptop mark */}
      <g transform="translate(0 -124)">
        <rect x={-30} y={-20} width={60} height={38} rx={4} fill="var(--wood)" {...INK} />
        <rect x={-24} y={-14} width={48} height={26} fill="var(--noren-mark)" {...THIN} />
        <g shapeRendering="crispEdges">
          <rect x={-12} y={-9} width={24} height={13} fill="var(--screen)" />
          <rect x={-9} y={-6} width={8} height={2} fill="var(--screen-ink)" />
          <rect x={-9} y={-2} width={13} height={2} fill="var(--screen-ink)" />
          <rect x={-16} y={5} width={32} height={3} fill="var(--wood-lo)" />
        </g>
      </g>
      <LightPool cx={0} cy={14} rx={70} ry={22} />
      {/* mailbox */}
      <g transform="translate(-58 0)">
        <rect x={-2} y={-4} width={4} height={18} fill="var(--wood-lo)" {...THIN} />
        <rect x={-10} y={-18} width={20} height={14} rx={4} fill="var(--lantern)" {...THIN} />
        <rect x={-6} y={-13} width={12} height={2} fill="var(--outline)" />
      </g>
      {/* potted plant */}
      <g transform="translate(54 2)" shapeRendering="crispEdges">
        <rect x={-8} y={-2} width={16} height={12} fill="var(--wood)" stroke="var(--outline)" strokeWidth={2} />
        <rect x={-6} y={-14} width={4} height={12} fill="var(--tree)" />
        <rect x={0} y={-20} width={4} height={18} fill="var(--tree-hi)" />
        <rect x={5} y={-12} width={4} height={10} fill="var(--tree)" />
      </g>
    </g>
  );
}
