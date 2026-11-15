import { forwardRef, useCallback, useImperativeHandle, useRef, type MouseEvent } from 'react';
import './world.css';
import { Avatar } from './Avatar';
import { RamenShopExterior, VIEW_H, VIEW_W } from './RamenShopExterior';
import { ramenShop } from './places';
import { useAvatarWalk } from './useAvatarWalk';
import { clampToYard, isOnShop, OUTSIDE_DOOR } from './walkable';

export interface TownSceneHandle {
  /** Focus the control that launches a place (used when its scene closes). */
  focusPlace: () => void;
  /** Stand the avatar outside the shop door, e.g. after leaving the shop. */
  standOutsideShop: () => void;
}

interface Props {
  /** True while a place's scene is open over the map. */
  placeOpen: boolean;
  reducedMotion: boolean;
  onOpenPlace: () => void;
}

/** The map. In this slice: the ramen shop, its labelled entry control and the optional walkable avatar. */
export const TownScene = forwardRef<TownSceneHandle, Props>(function TownScene({ placeOpen, reducedMotion, onOpenPlace }, ref) {
  const sceneRef = useRef<HTMLDivElement>(null);
  const avatarRef = useRef<HTMLDivElement>(null);
  const placeButtonRef = useRef<HTMLButtonElement>(null);

  const { pose, walkTo, placeAt } = useAvatarWalk({
    sceneRef,
    avatarRef,
    keysEnabled: !placeOpen,
    reducedMotion,
    onEnterDoor: onOpenPlace,
  });

  useImperativeHandle(ref, () => ({
    // preventScroll: returning focus must not move the map from where the visitor left it.
    focusPlace: () => placeButtonRef.current?.focus({ preventScroll: true }),
    standOutsideShop: () => placeAt(OUTSIDE_DOOR),
  }));

  /** Selecting the place opens it at once; the walk to the door is decoration and never delays content. */
  const selectPlace = useCallback(() => {
    onOpenPlace();
    walkTo(OUTSIDE_DOOR);
  }, [onOpenPlace, walkTo]);

  const onSceneClick = (e: MouseEvent<HTMLDivElement>) => {
    if ((e.target as HTMLElement).closest('button')) return;
    const box = e.currentTarget.getBoundingClientRect();
    const point = { x: ((e.clientX - box.left) / box.width) * VIEW_W, y: ((e.clientY - box.top) / box.height) * VIEW_H };
    if (isOnShop(point)) selectPlace();
    else walkTo(clampToYard(point));
  };

  return (
    <div
      ref={sceneRef}
      className="scene"
      role="group"
      aria-label="Town map. Optional: walk Kushal with the arrow keys or W A S D, or tap the ground."
      tabIndex={0}
      onClick={onSceneClick}
    >
      <RamenShopExterior className="scene__art" />
      <Avatar ref={avatarRef} pose={pose} />
      <button ref={placeButtonRef} type="button" className="place-label" aria-haspopup="dialog" onClick={selectPlace}>
        {ramenShop.label}
        <span className="place-label__hint">{ramenShop.hint}</span>
      </button>
    </div>
  );
});
