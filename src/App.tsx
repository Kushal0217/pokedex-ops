import { useCallback, useRef, useState } from 'react';
import './app.css';
import { FactsDialog } from './features/facts/FactsDialog';
import { facts } from './features/facts/facts';
import { AirportPreview } from './features/flights/AirportPreview';
import { BowlMark, FoodMenu } from './features/food/FoodMenu';
import { RamenInterior } from './features/food/RamenInterior';
import { ProfilePanel } from './features/profile/ProfilePanel';
import { StadiumPreview } from './features/stadium/StadiumPreview';
import { TownScene, type TownSceneHandle } from './features/world/TownScene';
import { placeById, type PlaceId } from './features/world/places';
import { LightingSelector } from './shared/ui/LightingSelector';
import { SceneDialog } from './shared/ui/SceneDialog';
import { useMediaQuery } from './shared/useMediaQuery';
import { useReducedMotion } from './shared/useReducedMotion';
import { useLighting } from './theme/timeOfDay';

const FACTS_HASH = '#facts';

/** One-line description of each place's scene, read out with its title. */
const SCENE_DESCRIPTION: Record<PlaceId, string> = {
  profile: 'A short introduction to Kushal and a link to the resume.',
  ramen: "Inside the ramen shop. Open the menu board to read Kushal's food favorites.",
  stadium: "Kushal's soccer club. The penalty game is not built yet.",
  airport: 'The flight log is not built yet.',
};

export function App() {
  const reducedMotion = useReducedMotion();
  // Phones get the vertical village path; wider screens get the broad town. Same places either way.
  const layoutId = useMediaQuery('(max-width: 760px)') ? 'path' : 'town';
  const lighting = useLighting();
  const [openPlace, setOpenPlace] = useState<PlaceId | null>(null);
  /** The place whose scene is on screen; kept while it closes so focus can return to it. */
  const lastPlace = useRef<PlaceId>('ramen');
  const [menuOpen, setMenuOpen] = useState(false);
  // A direct link to #facts opens the plain view straight away.
  const [factsOpen, setFactsOpen] = useState(() => window.location.hash === FACTS_HASH);

  const townRef = useRef<TownSceneHandle>(null);
  const menuButtonRef = useRef<HTMLButtonElement>(null);
  /** The control that opened the facts view, so focus can go back to it. */
  const factsLauncher = useRef<HTMLElement | null>(null);
  const headerFactsButton = useRef<HTMLButtonElement>(null);

  const openFacts = useCallback(() => {
    factsLauncher.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    setFactsOpen(true);
  }, []);

  const onOpenPlace = useCallback((id: PlaceId) => {
    lastPlace.current = id;
    setOpenPlace(id);
  }, []);

  const onPlaceChange = (open: boolean) => {
    if (open) return;
    setOpenPlace(null);
    setMenuOpen(false);
    townRef.current?.standOutside(lastPlace.current);
  };

  const factsAction = (
    <button type="button" className="dialog__action" onClick={openFacts}>
      Just the facts
    </button>
  );
  const shown = openPlace ?? lastPlace.current;

  return (
    <>
      <header className="topbar">
        <div className="topbar__inner">
          <div className="topbar__id">
            <h1 className="topbar__name">{facts.name}</h1>
            <p className="topbar__role">{facts.role}</p>
          </div>
          <button ref={headerFactsButton} type="button" className="facts-button" aria-haspopup="dialog" onClick={openFacts}>
            Just the facts
            <span className="facts-button__sub">resume &amp; contact</span>
          </button>
        </div>
      </header>

      <main className="page">
        <div className="page__intro">
          <p className="explore">
            <strong>Explore.</strong> Pick a place on the map. Walking is optional: arrow keys or W A S D, or tap the
            ground.
          </p>
          <LightingSelector value={lighting.preference} mode={lighting.mode} onChange={lighting.setPreference} />
        </div>

        <TownScene ref={townRef} layoutId={layoutId} placeOpen={openPlace !== null} reducedMotion={reducedMotion} onOpenPlace={onOpenPlace} />
      </main>

      <SceneDialog
        open={openPlace !== null}
        onOpenChange={onPlaceChange}
        title={placeById(shown).label}
        description={SCENE_DESCRIPTION[shown]}
        closeLabel="Back to town"
        size={shown === 'ramen' ? 'wide' : 'narrow'}
        actions={factsAction}
        onReturnFocus={() => townRef.current?.focusPlace(lastPlace.current)}
      >
        {shown === 'ramen' && <RamenInterior ref={menuButtonRef} onOpenMenu={() => setMenuOpen(true)} />}
        {shown === 'profile' && <ProfilePanel onOpenFacts={openFacts} />}
        {shown === 'stadium' && <StadiumPreview />}
        {shown === 'airport' && <AirportPreview />}
      </SceneDialog>

      <SceneDialog
        open={menuOpen}
        onOpenChange={setMenuOpen}
        title="Menu"
        description="Kushal's food favorites: real restaurants."
        closeLabel="Close menu"
        tone="menu"
        size="narrow"
        mark={<BowlMark />}
        actions={factsAction}
        onReturnFocus={() => menuButtonRef.current?.focus({ preventScroll: true })}
      >
        <FoodMenu />
      </SceneDialog>

      <FactsDialog
        open={factsOpen}
        onOpenChange={setFactsOpen}
        onReturnFocus={() => {
          const launcher = factsLauncher.current;
          (launcher && launcher.isConnected ? launcher : headerFactsButton.current)?.focus({ preventScroll: true });
        }}
      />
    </>
  );
}
