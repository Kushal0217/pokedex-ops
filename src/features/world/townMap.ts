import { places, type Layout, type PlaceId, type Rect } from './places';

export interface Point {
  x: number;
  y: number;
}

export interface Door {
  id: PlaceId;
  /** Doorway strip the avatar may step up into. */
  x1: number;
  x2: number;
  /** Crossing above this line while steering enters the place. */
  yEnter: number;
  /** Where the avatar stands just outside. */
  outside: Point;
}

/** Everything the avatar needs to know about one layout: bounds, obstacles, doors and routes. */
export interface TownMap {
  width: number;
  height: number;
  start: Point;
  doors: readonly Door[];
  isWalkable: (p: Point) => boolean;
  /** The place whose building covers this point, for tap-to-enter. */
  placeAt: (p: Point) => PlaceId | null;
  /** Waypoints from one point to (near) another, avoiding obstacles. Empty when no route exists. */
  route: (from: Point, to: Point) => Point[];
}

const EDGE = 14;
const DOOR_HALF = 30;
const CELL = 10;

const inside = (r: Rect, p: Point) => p.x > r.x1 && p.x < r.x2 && p.y > r.y1 && p.y < r.y2;
const shift = (r: Rect, d: Point): Rect => ({ x1: r.x1 + d.x, y1: r.y1 + d.y, x2: r.x2 + d.x, y2: r.y2 + d.y });

export function buildTownMap(layout: Layout): TownMap {
  const buildings = places.map((place) => ({ id: place.id, rect: shift(place.footprint, place.door[layout.id]) }));
  const solid: Rect[] = [
    ...places.flatMap((place) => (place.props ?? []).map((r) => shift(r, place.door[layout.id]))),
    // Trees block their whole canopy so the avatar is never drawn on top of one from behind.
    ...layout.trees.map((t) => ({ x1: t.x - 30 * t.s, y1: t.y - 38 * t.s, x2: t.x + 30 * t.s, y2: t.y + 54 * t.s })),
  ];
  const doors: Door[] = places.map((place) => {
    const d = place.door[layout.id];
    return { id: place.id, x1: d.x - DOOR_HALF, x2: d.x + DOOR_HALF, yEnter: d.y - 2, outside: { x: d.x, y: d.y + 20 } };
  });

  const isWalkable = (p: Point): boolean => {
    if (p.x < EDGE || p.x > layout.width - EDGE || p.y < 80 || p.y > layout.height - 6) return false;
    if (solid.some((r) => inside(r, p))) return false;
    const building = buildings.find((b) => inside(b.rect, p));
    if (!building) return true;
    // Inside a footprint only the doorway notch is open.
    const door = doors.find((d) => d.id === building.id)!;
    return p.x >= door.x1 && p.x <= door.x2 && p.y >= door.yEnter - 6;
  };

  const placeAt = (p: Point) => buildings.find((b) => inside(b.rect, p))?.id ?? null;

  // Coarse grid for routing.
  const cols = Math.ceil(layout.width / CELL);
  const rows = Math.ceil(layout.height / CELL);
  const centre = (c: number, r: number): Point => ({ x: c * CELL + CELL / 2, y: r * CELL + CELL / 2 });
  const open = new Uint8Array(cols * rows);
  for (let r = 0; r < rows; r += 1) for (let c = 0; c < cols; c += 1) open[r * cols + c] = isWalkable(centre(c, r)) ? 1 : 0;

  const nearestOpen = (p: Point): number => {
    const c0 = Math.min(cols - 1, Math.max(0, Math.floor(p.x / CELL)));
    const r0 = Math.min(rows - 1, Math.max(0, Math.floor(p.y / CELL)));
    let best = -1;
    let bestD = Infinity;
    for (let radius = 0; radius < Math.max(cols, rows) && best < 0; radius += 1) {
      for (let r = r0 - radius; r <= r0 + radius; r += 1) {
        for (let c = c0 - radius; c <= c0 + radius; c += 1) {
          if (r < 0 || c < 0 || r >= rows || c >= cols || !open[r * cols + c]) continue;
          const q = centre(c, r);
          const d = (q.x - p.x) ** 2 + (q.y - p.y) ** 2;
          if (d < bestD) {
            bestD = d;
            best = r * cols + c;
          }
        }
      }
    }
    return best;
  };

  const STEPS: readonly (readonly [number, number, number])[] = [
    [1, 0, 1], [-1, 0, 1], [0, 1, 1], [0, -1, 1], [1, 1, 1.414], [1, -1, 1.414], [-1, 1, 1.414], [-1, -1, 1.414],
  ];

  /** A* over the grid; small enough (a few thousand cells) to run on demand. */
  const route = (from: Point, to: Point): Point[] => {
    const startCell = nearestOpen(from);
    const goalCell = nearestOpen(to);
    if (startCell < 0 || goalCell < 0) return [];
    const goal = centre(goalCell % cols, Math.floor(goalCell / cols));
    const cost = new Float32Array(cols * rows).fill(Infinity);
    const cameFrom = new Int32Array(cols * rows).fill(-1);
    const done = new Uint8Array(cols * rows);
    const queue: number[] = [startCell];
    const score = new Float32Array(cols * rows).fill(Infinity);
    cost[startCell] = 0;
    score[startCell] = 0;
    while (queue.length > 0) {
      let bestIndex = 0;
      for (let i = 1; i < queue.length; i += 1) if (score[queue[i]!]! < score[queue[bestIndex]!]!) bestIndex = i;
      const current = queue.splice(bestIndex, 1)[0]!;
      if (current === goalCell) break;
      if (done[current]) continue;
      done[current] = 1;
      const c = current % cols;
      const r = Math.floor(current / cols);
      for (const [dc, dr, weight] of STEPS) {
        const nc = c + dc;
        const nr = r + dr;
        if (nc < 0 || nr < 0 || nc >= cols || nr >= rows) continue;
        const next = nr * cols + nc;
        if (!open[next] || done[next]) continue;
        // No cutting corners diagonally past a solid cell.
        if (dc !== 0 && dr !== 0 && (!open[r * cols + nc] || !open[nr * cols + c])) continue;
        const nextCost = cost[current]! + weight;
        if (nextCost < cost[next]!) {
          cost[next] = nextCost;
          cameFrom[next] = current;
          const q = centre(nc, nr);
          score[next] = nextCost + Math.hypot(q.x - goal.x, q.y - goal.y) / CELL;
          queue.push(next);
        }
      }
    }
    if (goalCell !== startCell && cameFrom[goalCell] === -1) return [];
    const cells: number[] = [];
    for (let cell = goalCell; cell !== -1 && cell !== startCell; cell = cameFrom[cell]!) cells.push(cell);
    const points = cells.reverse().map((cell) => centre(cell % cols, Math.floor(cell / cols)));
    // Finish exactly on the requested point when it is itself open ground.
    if (isWalkable(to)) points.push(to);
    return points;
  };

  return { width: layout.width, height: layout.height, start: layout.start, doors, isWalkable, placeAt, route };
}

/**
 * Moves from `from` by (dx, dy), sliding along obstacles: each axis is tried
 * on its own so walking diagonally into a wall still moves along it.
 */
export function step(map: TownMap, from: Point, dx: number, dy: number): Point {
  let next = { ...from };
  if (dx !== 0 && map.isWalkable({ x: next.x + dx, y: next.y })) next = { x: next.x + dx, y: next.y };
  if (dy !== 0 && map.isWalkable({ x: next.x, y: next.y + dy })) next = { x: next.x, y: next.y + dy };
  return next;
}
