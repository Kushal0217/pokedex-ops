import { forwardRef } from 'react';
import { PixelSpriteGroup } from '../world/PixelSprite';
import { kushalFrame } from '../world/kushalSprite';

const INK = { stroke: '#33241f', strokeWidth: 3, strokeLinejoin: 'round' as const };
const THIN = { stroke: '#33241f', strokeWidth: 2, strokeLinejoin: 'round' as const };

function Lamp({ x }: { x: number }) {
  return (
    <g transform={`translate(${x} 18)`}>
      <rect x={-1} y={0} width={2} height={20} fill="#33241f" />
      <circle cx={0} cy={40} r={34} fill="#ffd978" opacity={0.16} />
      <circle cx={0} cy={40} r={22} fill="#ffd978" opacity={0.22} />
      <path d="M -16 38 L -9 20 H 9 L 16 38 Z" fill="#c6452f" {...THIN} />
      <rect x={-6} y={38} width={12} height={5} fill="#ffe9a8" {...THIN} />
    </g>
  );
}

function Stool({ x }: { x: number }) {
  return (
    <g transform={`translate(${x} 0)`}>
      <ellipse cx={3} cy={270} rx={17} ry={4} fill="#33241f" opacity={0.25} />
      <rect x={-3} y={222} width={6} height={46} fill="#5a3a2a" {...THIN} />
      <rect x={-12} y={262} width={24} height={5} rx={2} fill="#5a3a2a" {...THIN} />
      <rect x={-16} y={212} width={32} height={11} rx={4} fill="#c6452f" {...THIN} />
      <rect x={-12} y={214} width={12} height={3} fill="#e0664a" />
    </g>
  );
}

function Bowl({ x, y }: { x: number; y: number }) {
  return (
    <g transform={`translate(${x} ${y})`} shapeRendering="crispEdges">
      <rect x={-5} y={-22} width={2} height={7} fill="#fff8e6" opacity={0.8} />
      <rect x={1} y={-25} width={2} height={8} fill="#fff8e6" opacity={0.8} />
      <rect x={7} y={-21} width={2} height={6} fill="#fff8e6" opacity={0.8} />
      <rect x={-13} y={-13} width={26} height={3} fill="#f2c96a" />
      <rect x={-8} y={-13} width={4} height={3} fill="#e0664a" />
      <rect x={2} y={-13} width={5} height={3} fill="#6aa95f" />
      <rect x={-15} y={-10} width={30} height={4} fill="#2c467a" />
      <rect x={-13} y={-6} width={26} height={3} fill="#2c467a" />
      <rect x={-9} y={-3} width={18} height={3} fill="#223762" />
      <rect x={-15} y={-10} width={30} height={1} fill="#fbf2dc" />
    </g>
  );
}

/**
 * Ramen-shop interior: an original illustrated counter scene on a fixed warm
 * indoor palette, so it reads the same in every lighting mode. The wall menu
 * board is a real HTML button layered over the art.
 */
export const RamenInterior = forwardRef<HTMLButtonElement, { onOpenMenu: () => void }>(function RamenInterior({ onOpenMenu }, menuButtonRef) {
  return (
    <>
      <div className="interior">
        <svg className="interior__art" viewBox="0 0 480 280" aria-hidden="true" focusable="false">
          {/* wall */}
          <rect width={480} height={232} fill="#ecd3a4" />
          <g fill="#dcbf8a" shapeRendering="crispEdges">
            {[40, 80, 120, 160, 200, 240, 280, 320, 360, 400, 440].map((x) => (
              <rect key={x} x={x} y={18} width={2} height={142} />
            ))}
            <rect x={20} y={40} width={8} height={2} />
            <rect x={132} y={112} width={10} height={2} />
            <rect x={250} y={36} width={8} height={2} />
            <rect x={452} y={130} width={8} height={2} />
          </g>
          <rect x={-4} y={-4} width={488} height={22} fill="#6b432c" {...INK} />
          <rect x={0} y={12} width={480} height={3} fill="#4f3021" />

          {/* shelf with bowls, jars and a plant */}
          <rect x={36} y={92} width={236} height={8} fill="#8a5a3c" {...THIN} />
          <rect x={52} y={100} width={6} height={10} fill="#6b432c" />
          <rect x={250} y={100} width={6} height={10} fill="#6b432c" />
          <g shapeRendering="crispEdges">
            {[58, 92].map((x) => (
              <g key={x}>
                <rect x={x} y={84} width={26} height={8} fill="#fbf2dc" stroke="#33241f" strokeWidth={2} />
                <rect x={x + 2} y={78} width={22} height={6} fill="#fbf2dc" stroke="#33241f" strokeWidth={2} />
                <rect x={x + 4} y={72} width={18} height={6} fill="#fbf2dc" stroke="#33241f" strokeWidth={2} />
                <rect x={x + 2} y={86} width={22} height={2} fill="#c6452f" />
              </g>
            ))}
            {[138, 158, 178].map((x, i) => (
              <g key={x}>
                <rect x={x} y={70} width={12} height={22} fill={['#7aae58', '#e0a34a', '#9a5a3a'][i]} stroke="#33241f" strokeWidth={2} />
                <rect x={x + 3} y={62} width={6} height={8} fill="#33241f" />
                <rect x={x + 2} y={78} width={8} height={6} fill="#fbf2dc" />
              </g>
            ))}
            <rect x={222} y={78} width={22} height={14} fill="#b0764c" stroke="#33241f" strokeWidth={2} />
            <rect x={228} y={62} width={4} height={16} fill="#4f9150" />
            <rect x={234} y={56} width={4} height={22} fill="#6aa95f" />
            <rect x={224} y={68} width={4} height={10} fill="#6aa95f" />
            <rect x={240} y={66} width={4} height={12} fill="#4f9150" />
          </g>

          {/* cord and frame behind the menu board button */}
          <path d="M 330 18 L 375 30 L 420 18" fill="none" stroke="#33241f" strokeWidth={2} />
          <rect x={304} y={26} width={142} height={98} rx={4} fill="#8a5a3c" {...INK} />

          <Lamp x={110} />
          <Lamp x={240} />

          {/* back counter band with a steaming pot */}
          <rect x={0} y={128} width={480} height={34} fill="#d9b885" />
          <rect x={0} y={128} width={480} height={3} fill="#c4a06c" />
          <g shapeRendering="crispEdges">
            <rect x={40} y={110} width={3} height={10} fill="#fff8e6" opacity={0.7} />
            <rect x={50} y={104} width={3} height={14} fill="#fff8e6" opacity={0.7} />
            <rect x={60} y={110} width={3} height={10} fill="#fff8e6" opacity={0.7} />
            <rect x={30} y={124} width={44} height={36} fill="#8d909c" stroke="#33241f" strokeWidth={2} />
            <rect x={26} y={120} width={52} height={6} fill="#b9bcc6" stroke="#33241f" strokeWidth={2} />
            <rect x={34} y={130} width={6} height={24} fill="#b9bcc6" />
          </g>

          {/* counter */}
          <rect x={-4} y={160} width={488} height={18} fill="#c58a5a" {...INK} />
          <rect x={0} y={163} width={480} height={3} fill="#dba777" />
          <rect x={-4} y={178} width={488} height={56} fill="#8a5a3c" {...INK} />
          <g fill="#6b432c" shapeRendering="crispEdges">
            {[60, 120, 180, 240, 300, 360, 420].map((x) => (
              <rect key={x} x={x} y={180} width={3} height={52} />
            ))}
            <rect x={20} y={196} width={14} height={2} />
            <rect x={140} y={214} width={18} height={2} />
            <rect x={262} y={198} width={14} height={2} />
            <rect x={380} y={212} width={16} height={2} />
          </g>
          <Bowl x={150} y={160} />
          <Bowl x={262} y={160} />
          <g shapeRendering="crispEdges">
            <rect x={196} y={140} width={16} height={20} fill="#fbf2dc" stroke="#33241f" strokeWidth={2} />
            <rect x={199} y={126} width={2} height={16} fill="#6b432c" />
            <rect x={204} y={122} width={2} height={20} fill="#6b432c" />
            <rect x={208} y={128} width={2} height={14} fill="#6b432c" />
          </g>

          {/* floor */}
          <rect x={-4} y={234} width={488} height={50} fill="#7a5642" {...INK} />
          <g fill="#644434" shapeRendering="crispEdges">
            <rect x={0} y={250} width={480} height={2} />
            <rect x={0} y={266} width={480} height={2} />
            {[70, 210, 350].map((x) => <rect key={x} x={x} y={236} width={2} height={14} />)}
            {[140, 280, 420].map((x) => <rect key={x} x={x} y={252} width={2} height={14} />)}
          </g>

          <Stool x={96} />
          <Stool x={206} />
          <Stool x={316} />

          {/* Kushal, at the counter */}
          <ellipse cx={398} cy={272} rx={20} ry={5} fill="#33241f" opacity={0.25} />
          <PixelSpriteGroup sprite={kushalFrame('up', 0)} x={377} y={199} px={1.75} />
        </svg>

        <button ref={menuButtonRef} type="button" className="interior__menu-button" aria-haspopup="dialog" onClick={onOpenMenu}>
          Menu
          <small>read the favorites</small>
        </button>
      </div>
      <p className="interior__caption">A small ramen counter. The menu board lists Kushal’s real food favorites.</p>
    </>
  );
});
