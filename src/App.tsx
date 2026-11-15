import { useCallback, useEffect, useRef, useState } from 'react';
import './app.css';
import { FactsDialog } from './features/facts/FactsDialog';
import { facts } from './features/facts/facts';
import { BowlMark, FoodMenu } from './features/food/FoodMenu';
import { RamenInterior } from './features/food/RamenInterior';
import { LightingPreviewSelector } from './features/preview/LightingPreviewSelector';
import { TownScene, type TownSceneHandle } from './features/world/TownScene';
import { ramenShop } from './features/world/places';
import { SceneDialog } from './shared/ui/SceneDialog';
import { useReducedMotion } from './shared/useReducedMotion';
import { applyTimeMode, type TimeMode } from './theme/timeOfDay';

const FACTS_HASH = '#facts';

export function App() {
  const reducedMotion = useReducedMotion();
  const [mode, setMode] = useState<TimeMode>('day');
  const [interiorOpen, setInteriorOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  // A direct link to #facts opens the plain view straight away.
  const [factsOpen, setFactsOpen] = useState(() => window.location.hash === FACTS_HASH);

  const townRef = useRef<TownSceneHandle>(null);
  const menuButtonRef = useRef<HTMLButtonElement>(null);
  /** The control that opened the facts view, so focus can go back to it. */
  const factsLauncher = useRef<HTMLElement | null>(null);
  const headerFactsButton = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    applyTimeMode(mode);
  }, [mode]);

  const openFacts = useCallback(() => {
    factsLauncher.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    setFactsOpen(true);
  }, []);

  const onInteriorChange = (open: boolean) => {
    setInteriorOpen(open);
    if (!open) {
      setMenuOpen(false);
      townRef.current?.standOutsideShop();
    }
  };

  const factsAction = (
    <button type="button" className="dialog__action" onClick={openFacts}>
      Just the facts
    </button>
  );

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
          <LightingPreviewSelector value={mode} onChange={setMode} />
        </div>

        <TownScene ref={townRef} placeOpen={interiorOpen} reducedMotion={reducedMotion} onOpenPlace={() => setInteriorOpen(true)} />
      </main>

      <SceneDialog
        open={interiorOpen}
        onOpenChange={onInteriorChange}
        title={ramenShop.label}
        description="Inside the ramen shop. Open the menu board to read Kushal's food favorites."
        closeLabel="Back to town"
        actions={factsAction}
        onReturnFocus={() => townRef.current?.focusPlace()}
      >
        <RamenInterior ref={menuButtonRef} onOpenMenu={() => setMenuOpen(true)} />
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
