import { useCallback, useEffect, useRef, useState, type RefObject } from 'react';
import { VIEW_H, VIEW_W } from './RamenShopExterior';
import { DOOR, START, step, type Point } from './walkable';

export type Facing = 'down' | 'up' | 'left' | 'right';
export interface Pose {
  facing: Facing;
  /** 0 idle, 1 and 2 are the two walking steps. */
  frame: 0 | 1 | 2;
}

/** Avatar box in scene units: sprite is 24 x 42 sprite pixels plus a shadow row. */
export const AVATAR_W = 42;
export const AVATAR_H = 77;
const SPEED = 95; // scene units per second
const STEP_MS = 150;

const KEY_DIRS: Record<string, readonly [number, number]> = {
  ArrowUp: [0, -1], ArrowDown: [0, 1], ArrowLeft: [-1, 0], ArrowRight: [1, 0],
  w: [0, -1], s: [0, 1], a: [-1, 0], d: [1, 0],
};

interface Options {
  /** The scene element: arrow keys only steer while focus is inside it, so they still scroll the page elsewhere. */
  sceneRef: RefObject<HTMLElement | null>;
  avatarRef: RefObject<HTMLElement | null>;
  /** False while a dialog is open: keys are ignored, a decorative walk may finish. */
  keysEnabled: boolean;
  reducedMotion: boolean;
  /** Called once when the avatar is walked up into the doorway. */
  onEnterDoor: () => void;
}

/**
 * Optional avatar movement: WASD / arrow keys, or walk to a tapped point.
 * Position lives in a ref and is written straight to the element's style, so
 * React re-renders only when the pose (facing or step frame) changes.
 */
export function useAvatarWalk({ sceneRef, avatarRef, keysEnabled, reducedMotion, onEnterDoor }: Options) {
  const pos = useRef<Point>({ ...START });
  const [pose, setPose] = useState<Pose>({ facing: 'down', frame: 0 });
  const poseRef = useRef(pose);
  const keys = useRef(new Set<string>());
  const target = useRef<(Point & { enter: boolean }) | null>(null);
  const raf = useRef(0);
  const last = useRef(0);
  const live = useRef({ keysEnabled, reducedMotion, onEnterDoor });
  live.current = { keysEnabled, reducedMotion, onEnterDoor };

  const place = useCallback(() => {
    const el = avatarRef.current;
    if (!el) return;
    el.style.left = `${((pos.current.x - AVATAR_W / 2) / VIEW_W) * 100}%`;
    el.style.top = `${((pos.current.y - AVATAR_H + 4) / VIEW_H) * 100}%`;
  }, [avatarRef]);

  const applyPose = useCallback((next: Pose) => {
    if (next.facing === poseRef.current.facing && next.frame === poseRef.current.frame) return;
    poseRef.current = next;
    setPose(next);
  }, []);

  const stop = useCallback(() => {
    cancelAnimationFrame(raf.current);
    raf.current = 0;
    applyPose({ facing: poseRef.current.facing, frame: 0 });
  }, [applyPose]);

  const tick = useCallback(
    (now: number) => {
      const dt = Math.min(0.05, (now - last.current) / 1000);
      last.current = now;
      let dx = 0;
      let dy = 0;
      if (live.current.keysEnabled && keys.current.size > 0) {
        target.current = null;
        for (const key of keys.current) {
          const dir = KEY_DIRS[key];
          if (dir) {
            dx += dir[0];
            dy += dir[1];
          }
        }
      } else if (target.current) {
        dx = target.current.x - pos.current.x;
        dy = target.current.y - pos.current.y;
        if (Math.hypot(dx, dy) < 2) {
          target.current = null;
          dx = 0;
          dy = 0;
        }
      }
      const length = Math.hypot(dx, dy);
      if (length === 0) {
        stop();
        return;
      }
      const distance = Math.min(SPEED * dt, target.current ? length : Infinity);
      const before = pos.current;
      let after = step(before, (dx / length) * distance, (dy / length) * distance);
      // Walking to a tapped point: if something is in the way sideways, detour down into the open yard.
      if (target.current && after.x === before.x && Math.abs(dx) > 2) after = step(before, 0, distance);
      const blocked = after.x === before.x && after.y === before.y;
      pos.current = after;
      place();

      const facing: Facing = Math.abs(dx) > Math.abs(dy) ? (dx > 0 ? 'right' : 'left') : dy > 0 ? 'down' : 'up';
      const frame = live.current.reducedMotion ? 0 : Math.floor(now / STEP_MS) % 2 === 0 ? 1 : 2;
      applyPose({ facing, frame });

      const steeredIn = !target.current || target.current.enter;
      if (steeredIn && after.y <= DOOR.yEnter && before.y > DOOR.yEnter) {
        target.current = null;
        keys.current.clear();
        stop();
        live.current.onEnterDoor();
        return;
      }
      if (blocked && target.current) target.current = null;
      raf.current = requestAnimationFrame(tick);
    },
    [applyPose, place, stop],
  );

  const start = useCallback(() => {
    if (raf.current) return;
    last.current = performance.now();
    raf.current = requestAnimationFrame(tick);
  }, [tick]);

  /** Walk to a point. With reduced motion the avatar is simply placed there. */
  const walkTo = useCallback(
    (point: Point, options: { enter?: boolean } = {}) => {
      if (live.current.reducedMotion) {
        target.current = null;
        pos.current = { ...point };
        place();
        applyPose({ facing: 'down', frame: 0 });
        if (options.enter) live.current.onEnterDoor();
        return;
      }
      target.current = { ...point, enter: options.enter ?? false };
      start();
    },
    [applyPose, place, start],
  );

  /** Put the avatar somewhere immediately, facing the visitor. */
  const placeAt = useCallback(
    (point: Point) => {
      target.current = null;
      keys.current.clear();
      pos.current = { ...point };
      place();
      stop();
      applyPose({ facing: 'down', frame: 0 });
    },
    [applyPose, place, stop],
  );

  useEffect(() => {
    place();
  }, [place]);

  useEffect(() => {
    const isTyping = (el: EventTarget | null) =>
      el instanceof HTMLElement && (el.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName));
    const keyOf = (e: KeyboardEvent) => (e.key.length === 1 ? e.key.toLowerCase() : e.key);

    const onKeyDown = (e: KeyboardEvent) => {
      if (!live.current.keysEnabled || e.metaKey || e.ctrlKey || e.altKey) return;
      const key = keyOf(e);
      if (!KEY_DIRS[key]) return;
      const isArrow = key.startsWith('Arrow');
      if (isArrow) {
        // Arrow keys steer only while focus is in the scene; elsewhere they scroll or change radios as usual.
        if (!sceneRef.current?.contains(document.activeElement)) return;
        e.preventDefault();
      } else if (isTyping(e.target)) {
        return;
      }
      keys.current.add(key);
      start();
    };
    const onKeyUp = (e: KeyboardEvent) => keys.current.delete(keyOf(e));
    const release = () => keys.current.clear();

    window.addEventListener('keydown', onKeyDown);
    window.addEventListener('keyup', onKeyUp);
    window.addEventListener('blur', release);
    document.addEventListener('visibilitychange', release);
    return () => {
      window.removeEventListener('keydown', onKeyDown);
      window.removeEventListener('keyup', onKeyUp);
      window.removeEventListener('blur', release);
      document.removeEventListener('visibilitychange', release);
      cancelAnimationFrame(raf.current);
      raf.current = 0;
    };
  }, [sceneRef, start]);

  useEffect(() => {
    if (!keysEnabled) keys.current.clear();
  }, [keysEnabled]);

  return { pose, walkTo, placeAt };
}
