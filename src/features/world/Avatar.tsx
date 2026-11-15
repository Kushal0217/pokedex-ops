import { forwardRef } from 'react';
import { spriteRuns } from './PixelSprite';
import { kushalFrame } from './kushalSprite';
import { AVATAR_W, type Pose } from './useAvatarWalk';

/** Kushal's movable sprite, layered over the scene art. Decorative: never required for navigation. */
export const Avatar = forwardRef<HTMLDivElement, { pose: Pose; sceneWidth: number }>(function Avatar({ pose, sceneWidth }, ref) {
  const direction = pose.facing === 'left' || pose.facing === 'right' ? 'side' : pose.facing;
  const sprite = kushalFrame(direction, pose.frame);
  return (
    <div ref={ref} className="avatar" style={{ width: `${(AVATAR_W / sceneWidth) * 100}%` }} data-facing={pose.facing} data-frame={pose.frame}>
      <span className="avatar__name">Kushal</span>
      <svg viewBox="0 0 24 44" aria-hidden="true" shapeRendering="crispEdges">
        <ellipse cx={12} cy={41.6} rx={11} ry={2.4} fill="var(--cast-shadow)" opacity="var(--cast-shadow-o)" shapeRendering="auto" />
        <g transform={pose.facing === 'left' ? 'translate(24 0) scale(-1 1)' : undefined}>
          {spriteRuns(sprite).map((r) => (
            <rect key={`${r.x}-${r.y}`} x={r.x} y={r.y} width={r.w} height={1} fill={r.fill} />
          ))}
        </g>
      </svg>
    </div>
  );
});
