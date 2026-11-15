import { useCallback, useEffect, useRef, useState, type RefObject } from 'react';
import type { PlaceId } from './places';
import { step, type Point, type TownMap } from './townMap';

export type Facing = 'down' | 'up' | 'left' | 'right';
export interface Pose {
  facing: Facing;
  /** 0 idle, 1 and 2 are the two walking steps. */
  frame: 0 | 1 | 2;
}

/** Avatar box in scene units: sprite is 24 x 42 sprite pixels plus a shadow row. */
export const AVATAR_W = 42;
export const AVATAR_H = 77;
const SPEED = 120; // scene units per second
const STEP_MS = 150;

const KEY_DIRS: Record<string, readonly [number, number]> = {
  ArrowUp: [0, -1], ArrowDown: [0, 1], ArrowLeft: [-1, 0], ArrowRight: [1, 0],
  w: [0, -1], s: [0, 1], a: [-1, 0], d: [1, 0],
};

interface Options {
  map: TownMap;
  /** The scene element: arrow keys only steer while focus is inside it, so they still scroll the page elsewhere. */
  sceneRef: RefObject<HTMLElement | null>;
  avatarRef: RefObject<HTMLElement | null>;
  /** False while a dialog is open: keys are ignored, a decorative walk may finish. */
  keysEnabled: boolean;
  reducedMotion: boolean;
  /** Called once when the avatar is steered up into a doorway. */
  onEnterDoor: (place: PlaceId) => void;
}

/**
 * Optional avatar movement: WASD / arrow keys, or walk to a tapped point along
 * a route around obstacles. Position lives in a ref and is written straight to
 * the element's style, so React re-renders only when the pose changes.
 */
export function useAvatarWalk({ map, sceneRef, avatarRef, keysEnabled, reducedMotion, onEnterDoor }: Options) {
  const pos = useRef<Point>({ ...map.start });
  const [pose, setPose] = useState<Pose>({ facing: 'down', frame: 0 });
  const poseRef = useRef(pose);
  const keys = useRef(new Set<string>());
  /** Remaining waypoints of a tap/selection walk. */
  const path = useRef<Point[]>([]);
  const raf = useRef(0);
  const last = useRef(0);
  const live = useRef({ map, keysEnabled, reducedMotion, onEnterDoor });
  live.current = { map, keysEnabled, reducedMotion, onEnterDoor };

  const place = useCallback(() => {
    const el = avatarRef.current;
    if (!el) return;
    const { width, height } = live.current.map;
    el.style.left = `${((pos.current.x - AVATAR_W / 2) / width) * 100}%`;
    el.style.top = `${((pos.current.y - AVATAR_H + 4) / height) * 100}%`;
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
      const { map: town } = live.current;
      const steering = live.current.keysEnabled && keys.current.size > 0;
      let dx = 0;
      let dy = 0;
      if (steering) {
        path.current = [];
        for (const key of keys.current) {
          const dir = KEY_DIRS[key];
          if (dir) {
            dx += dir[0];
            dy += dir[1];
          }
        }
      } else {
        while (path.current.length > 0) {
          const next = path.current[0]!;
          dx = next.x - pos.current.x;
          dy = next.y - pos.current.y;
          if (Math.hypot(dx, dy) >= 2) break;
          path.current.shift();
          dx = 0;
          dy = 0;
        }
      }
      const length = Math.hypot(dx, dy);
      if (length === 0) {
        stop();
        return;
      }
      const distance = Math.min(SPEED * dt, steering ? Infinity : length);
      const before = pos.current;
      const after = step(town, before, (dx / length) * distance, (dy / length) * distance);
      const blocked = after.x === before.x && after.y === before.y;
      pos.current = after;
      place();

      const facing: Facing = Math.abs(dx) > Math.abs(dy) ? (dx > 0 ? 'right' : 'left') : dy > 0 ? 'down' : 'up';
      const frame = live.current.reducedMotion ? 0 : Math.floor(now / STEP_MS) % 2 === 0 ? 1 : 2;
      applyPose({ facing, frame });

      if (steering) {
        const door = town.doors.find((d) => after.x >= d.x1 && after.x <= d.x2 && after.y <= d.yEnter && before.y > d.yEnter);
        if (door) {
          keys.current.clear();
          stop();
          live.current.onEnterDoor(door.id);
          return;
        }
      } else if (blocked) {
        path.current = [];
      }
      raf.current = requestAnimationFrame(tick);
    },
    [applyPose, place, stop],
  );

  const start = useCallback(() => {
    if (raf.current) return;
    last.current = performance.now();
    raf.current = requestAnimationFrame(tick);
  }, [tick]);

  /** Put the avatar somewhere immediately, facing the visitor. */
  const placeAt = useCallback(
    (point: Point) => {
      path.current = [];
      keys.current.clear();
      pos.current = { ...point };
      place();
      stop();
      applyPose({ facing: 'down', frame: 0 });
    },
    [applyPose, place, stop],
  );

  /** Walk to a point along a route. With reduced motion the avatar is simply placed there. */
  const walkTo = useCallback(
    (point: Point) => {
      const route = live.current.map.route(pos.current, point);
      if (route.length === 0) return;
      if (live.current.reducedMotion) {
        placeAt(route[route.length - 1]!);
        return;
      }
      path.current = route;
      start();
    },
    [placeAt, start],
  );

  // A new layout (desktop town <-> phone path) restarts the avatar at that layout's start.
  useEffect(() => {
    placeAt(map.start);
  }, [map, placeAt]);

  useEffect(() => {
    const isTyping = (el: EventTarget | null) =>
      el instanceof HTMLElement && (el.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName));
    const keyOf = (e: KeyboardEvent) => (e.key.length === 1 ? e.key.toLowerCase() : e.key);

    const onKeyDown = (e: KeyboardEvent) => {
      if (!live.current.keysEnabled || e.metaKey || e.ctrlKey || e.altKey) return;
      const key = keyOf(e);
      if (!KEY_DIRS[key]) return;
      if (key.startsWith('Arrow')) {
        // Arrow keys steer only while focus is in the scene; elsewhere they scroll or change radios as usual.
        if (!sceneRef.current?.contains(document.activeElement)) return;
        e.preventDefault();
      } else if (isTyping(e.target) && (e.target as HTMLInputElement).type !== 'radio') {
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
