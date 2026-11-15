import './food.css';
import { beliProfileUrl, restaurants } from './restaurants';

/**
 * Kushal's real-world food favourites, as shown on the ramen shop's menu.
 * All entries are readable together. Missing ratings, notes and links are omitted.
 */
export function FoodMenu() {
  return (
    <div className="menu__body">
      <p className="menu__kicker">Kushal’s food favorites</p>
      <p className="menu__note">Real restaurants, served from a fictional ramen counter.</p>

      <ul className="menu__list">
        {restaurants.map((r) => (
          <li key={r.id} className="menu__item">
            <div className="menu__line">
              <span className="menu__name">
                {r.url ? (
                  <a href={r.url} target="_blank" rel="noreferrer">
                    {r.name}
                  </a>
                ) : (
                  r.name
                )}
              </span>
              <span className="menu__leader" aria-hidden="true" />
              <span className="menu__city">{r.city}</span>
            </div>
            {r.rating !== undefined && <p className="menu__meta">Kushal’s rating: {r.rating}</p>}
            {r.note && <p className="menu__meta">{r.note}</p>}
          </li>
        ))}
      </ul>

      <p className="menu__foot">More picks get added as Kushal shares them.</p>

      {beliProfileUrl && (
        <a className="menu__beli" href={beliProfileUrl} target="_blank" rel="noreferrer">
          Find me on Beli
        </a>
      )}
    </div>
  );
}

/** Small original bowl mark used as the menu's emblem. Decorative. */
export function BowlMark() {
  return (
    <svg className="menu__mark" viewBox="0 0 16 14" aria-hidden="true" shapeRendering="crispEdges">
      <rect x="5" y="0" width="1" height="3" fill="currentColor" opacity="0.7" />
      <rect x="8" y="1" width="1" height="3" fill="currentColor" opacity="0.7" />
      <rect x="11" y="0" width="1" height="3" fill="currentColor" opacity="0.7" />
      <rect x="1" y="5" width="14" height="2" fill="currentColor" />
      <rect x="2" y="7" width="12" height="2" fill="currentColor" />
      <rect x="3" y="9" width="10" height="2" fill="currentColor" />
      <rect x="5" y="11" width="6" height="2" fill="currentColor" />
    </svg>
  );
}
