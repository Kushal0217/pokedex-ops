/**
 * The town's places as content. Both layouts (the broad desktop town and the
 * vertical phone path) are generated from this one list, so adding a place
 * means adding an entry here plus, optionally, building art and a scene.
 */
export type PlaceId = 'profile' | 'ramen' | 'stadium' | 'airport';
export type LayoutId = 'town' | 'path';

export interface Rect {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

export interface Place {
  id: PlaceId;
  /** Visible label on the map. */
  label: string;
  /** Short hint shown with the label. */
  hint: string;
  category: string;
  /** Door position (bottom centre of the doorway) per layout, in scene units. */
  door: Record<LayoutId, { x: number; y: number }>;
  /** Solid ground area relative to the door: the avatar cannot stand inside it. */
  footprint: Rect;
  /** Extra solid props relative to the door. */
  props?: readonly Rect[];
}

export const places: readonly Place[] = [
  {
    id: 'profile',
    label: 'Profile',
    hint: 'who is Kushal',
    category: 'Work',
    door: { town: { x: 210, y: 250 }, path: { x: 150, y: 250 } },
    footprint: { x1: -116, y1: -186, x2: 120, y2: 6 },
  },
  {
    id: 'ramen',
    label: 'Ramen shop',
    hint: 'food favorites',
    category: 'Food',
    door: { town: { x: 770, y: 270 }, path: { x: 316, y: 640 } },
    footprint: { x1: -138, y1: -200, x2: 144, y2: 6 },
    props: [{ x1: 60, y1: 0, x2: 96, y2: 38 }],
  },
  {
    id: 'stadium',
    label: 'Stadium',
    hint: 'penalty kicks',
    category: 'Soccer',
    door: { town: { x: 240, y: 580 }, path: { x: 180, y: 1040 } },
    footprint: { x1: -170, y1: -218, x2: 180, y2: 6 },
  },
  {
    id: 'airport',
    label: 'Airport',
    hint: 'flight log',
    category: 'Travel',
    door: { town: { x: 770, y: 600 }, path: { x: 296, y: 1440 } },
    footprint: { x1: -164, y1: -232, x2: 178, y2: 6 },
  },
];

export function placeById(id: PlaceId): Place {
  const place = places.find((p) => p.id === id);
  if (!place) throw new Error(`Unknown place: ${id}`);
  return place;
}

export interface TreeSpot {
  x: number;
  y: number;
  s: number;
}

export interface Layout {
  id: LayoutId;
  width: number;
  height: number;
  /** Where the avatar starts (feet). */
  start: { x: number; y: number };
  /** Road centre lines; drawn as outlined strokes. Doors connect to these. */
  roads: readonly (readonly [number, number])[][];
  trees: readonly TreeSpot[];
}

export const layouts: Record<LayoutId, Layout> = {
  /** Desktop: a broad town around a central crossroads. */
  town: {
    id: 'town',
    width: 1000,
    height: 680,
    start: { x: 492, y: 372 },
    roads: [
      [[70, 330], [930, 330]],
      [[490, 330], [490, 644]],
      [[150, 644], [860, 644]],
      [[210, 250], [210, 330]],
      [[770, 270], [770, 330]],
      [[240, 580], [240, 644]],
      [[770, 600], [770, 644]],
    ],
    trees: [
      { x: 44, y: 70, s: 1 }, { x: 392, y: 96, s: 1.1 }, { x: 492, y: 200, s: 0.9 }, { x: 586, y: 84, s: 1 },
      { x: 958, y: 110, s: 0.95 }, { x: 40, y: 250, s: 0.8 }, { x: 962, y: 430, s: 0.9 }, { x: 38, y: 470, s: 0.9 },
      { x: 448, y: 470, s: 0.85 }, { x: 548, y: 520, s: 0.9 },
    ],
  },
  /** Phone: the same places along one winding vertical path. */
  path: {
    id: 'path',
    width: 480,
    height: 1540,
    start: { x: 240, y: 318 },
    roads: [
      [[150, 250], [150, 320], [420, 320], [420, 380]],
      [[420, 320], [60, 320], [60, 708], [316, 708], [316, 640]],
      [[316, 708], [430, 708], [430, 1108], [180, 1108], [180, 1040]],
      [[180, 1108], [56, 1108], [56, 1502], [296, 1502], [296, 1440]],
      [[296, 1502], [430, 1502]],
    ],
    trees: [
      { x: 330, y: 110, s: 1 }, { x: 430, y: 200, s: 0.85 }, { x: 110, y: 470, s: 0.9 }, { x: 60, y: 800, s: 0.7 },
      { x: 420, y: 1250, s: 0.7 }, { x: 60, y: 1010, s: 0.6 }, { x: 440, y: 800, s: 0.6 }, { x: 90, y: 1250, s: 0.6 },
    ],
  },
};
