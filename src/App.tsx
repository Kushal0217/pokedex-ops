import { useEffect, useState } from 'react';
import './features/world/world.css';
import './app.css';
import { FoodMenuPanel } from './features/food/FoodMenuPanel';
import { LightingPreviewSelector } from './features/preview/LightingPreviewSelector';
import { PixelSprite } from './features/world/PixelSprite';
import { RamenShopExterior } from './features/world/RamenShopExterior';
import { kushalSprite } from './features/world/kushalSprite';
import { applyTimeMode, type TimeMode } from './theme/timeOfDay';

const MENU_ID = 'ramen-menu';

/**
 * Slice 1: visual-foundation sample.
 * Avatar + ramen-shop exterior + open food menu, in day / evening / night.
 * The full town, interiors and navigation arrive in later slices.
 */
export function App() {
  const [mode, setMode] = useState<TimeMode>('day');
  const [menuOpen, setMenuOpen] = useState(true);

  useEffect(() => {
    applyTimeMode(mode);
  }, [mode]);

  return (
    <div className="page">
      <header className="masthead">
        <div className="masthead__id">
          <h1 className="masthead__name">Kushal Gaddam</h1>
          <p className="masthead__role">Software Engineer</p>
        </div>
        <LightingPreviewSelector value={mode} onChange={setMode} />
      </header>

      <main className="sample">
        <div className="scene">
          <RamenShopExterior className="scene__art" />
          <span className="nameplate">Kushal</span>
          <button
            type="button"
            className="place-label"
            aria-expanded={menuOpen}
            aria-controls={MENU_ID}
            onClick={() => setMenuOpen((open) => !open)}
          >
            Ramen shop
            <span className="place-label__hint">{menuOpen ? 'menu open' : 'open menu'}</span>
          </button>
        </div>

        <div className="sample__side">
          {menuOpen && <FoodMenuPanel id={MENU_ID} onClose={() => setMenuOpen(false)} />}

          <figure className="closeup">
            <PixelSprite sprite={kushalSprite} className="closeup__sprite" label="Kushal’s map sprite, enlarged" />
            <figcaption>
              <strong>Sprite close-up</strong>
              Hood up, black jacket, light blue jeans, white sneakers. Shown small on the map; enlarged here for
              review.
            </figcaption>
          </figure>
        </div>
      </main>

      <footer className="sample-note">Visual sample (Slice 1). The full town, interiors and navigation come next.</footer>
    </div>
  );
}
