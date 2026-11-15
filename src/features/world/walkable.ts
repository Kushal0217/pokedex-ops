import { VIEW_H, VIEW_W } from './RamenShopExterior';

/** Positions are the avatar's feet, in scene units (the exterior's viewBox). */
export interface Point {
  x: number;
  y: number;
}

/** Where the avatar starts and where it stands after leaving the shop. */
export const START: Point = { x: 226, y: 316 };
export const OUTSIDE_DOOR: Point = { x: 240, y: 270 };
/** Walking up into this strip enters the shop. */
export const DOOR = { x1: 204, x2: 276, yEnter: 251 };

const YARD_TOP = 258; // front edge of the building, bushes and forecourt
const MENU_STAND = { x1: 300, x2: 336, yBottom: 290 };

/** True when the avatar may stand at this point. */
export function isWalkable({ x, y }: Point): boolean {
  if (x < 14 || x > VIEW_W - 14 || y > VIEW_H - 6) return false;
  if (x > MENU_STAND.x1 && x < MENU_STAND.x2 && y < MENU_STAND.yBottom) return false;
  if (y >= YARD_TOP) return true;
  // Only the doorway is open above the yard line.
  return x >= DOOR.x1 && x <= DOOR.x2 && y >= DOOR.yEnter - 6;
}

/** True when the point is on the shop building itself (used for click-to-enter). */
export function isOnShop({ x, y }: Point): boolean {
  return x >= 104 && x <= 376 && y >= 58 && y < 252;
}

/** Nearest sensible standing point for a tap anywhere in the scene. */
export function clampToYard({ x, y }: Point): Point {
  return { x: Math.min(VIEW_W - 14, Math.max(14, x)), y: Math.min(VIEW_H - 6, Math.max(YARD_TOP, y)) };
}

/**
 * Moves from `from` by (dx, dy), sliding along obstacles: each axis is tried
 * on its own so walking diagonally into a wall still moves along it.
 */
export function step(from: Point, dx: number, dy: number): Point {
  let next = { ...from };
  if (dx !== 0 && isWalkable({ x: next.x + dx, y: next.y })) next = { x: next.x + dx, y: next.y };
  if (dy !== 0 && isWalkable({ x: next.x, y: next.y + dy })) next = { x: next.x, y: next.y + dy };
  return next;
}
