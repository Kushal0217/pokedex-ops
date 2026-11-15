import { forwardRef, useCallback, useImperativeHandle, useMemo, useRef, type MouseEvent } from 'react';
import './world.css';
import { Avatar } from './Avatar';
import { TownArt } from './TownArt';
import { layouts, places, type LayoutId, type PlaceId } from './places';
import { buildTownMap } from './townMap';
import { useAvatarWalk } from './useAvatarWalk';

export interface TownSceneHandle {
  /** Focus the control that launches a place (used when its scene closes). */
  focusPlace: (id: PlaceId) => void;
  /** Stand the avatar outside a place's door, e.g. after leaving it. */
  standOutside: (id: PlaceId) => void;
}

interface Props {
  /** 'town' on wide screens, 'path' on phones. Same places, art and interactions. */
  layoutId: LayoutId;
  /** True while a place's scene is open over the map. */
  placeOpen: boolean;
  reducedMotion: boolean;
  onOpenPlace: (id: PlaceId) => void;
}

/** The map: every place as art plus a labelled control, and the optional walkable avatar. */
export const TownScene = forwardRef<TownSceneHandle, Props>(function TownScene({ layoutId, placeOpen, reducedMotion, onOpenPlace }, ref) {
  const layout = layouts[layoutId];
  const map = useMemo(() => buildTownMap(layout), [layout]);
  const sceneRef = useRef<HTMLDivElement>(null);
  const avatarRef = useRef<HTMLDivElement>(null);
  const buttons = useRef(new Map<PlaceId, HTMLButtonElement>());

  const { pose, walkTo, placeAt } = useAvatarWalk({ map, sceneRef, avatarRef, keysEnabled: !placeOpen, reducedMotion, onEnterDoor: onOpenPlace });

  const outside = useCallback((id: PlaceId) => map.doors.find((d) => d.id === id)!.outside, [map]);

  useImperativeHandle(ref, () => ({
    // preventScroll: returning focus must not move the map from where the visitor left it.
    focusPlace: (id) => buttons.current.get(id)?.focus({ preventScroll: true }),
    standOutside: (id) => placeAt(outside(id)),
  }));

  /** Selecting a place opens it at once; the walk to its door is decoration and never delays content. */
  const selectPlace = useCallback(
    (id: PlaceId) => {
      onOpenPlace(id);
      walkTo(outside(id));
    },
    [onOpenPlace, outside, walkTo],
  );

  const onSceneClick = (e: MouseEvent<HTMLDivElement>) => {
    if ((e.target as HTMLElement).closest('button')) return;
    const box = e.currentTarget.getBoundingClientRect();
    const point = { x: ((e.clientX - box.left) / box.width) * layout.width, y: ((e.clientY - box.top) / box.height) * layout.height };
    const tapped = map.placeAt(point);
    if (tapped) selectPlace(tapped);
    else walkTo(point);
  };

  return (
    <div
      ref={sceneRef}
      className={`scene scene--${layoutId}`}
      role="group"
      aria-label="Town map. Optional: walk Kushal with the arrow keys or W A S D, or tap the ground."
      tabIndex={0}
      onClick={onSceneClick}
    >
      <TownArt layout={layout} map={map} />
      <Avatar ref={avatarRef} pose={pose} sceneWidth={layout.width} />
      {places.map((place) => {
        const door = place.door[layoutId];
        return (
          <button
            key={place.id}
            ref={(el) => {
              if (el) buttons.current.set(place.id, el);
              else buttons.current.delete(place.id);
            }}
            type="button"
            className="place-label"
            style={{ left: `${(door.x / layout.width) * 100}%`, top: `${((door.y + 16) / layout.height) * 100}%` }}
            aria-haspopup="dialog"
            onClick={() => selectPlace(place.id)}
          >
            {place.label}
            <span className="place-label__hint">{place.hint}</span>
          </button>
        );
      })}
    </div>
  );
});
