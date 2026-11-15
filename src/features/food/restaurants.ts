/**
 * Kushal's food favourites: a manually refreshed snapshot.
 *
 * To update: edit this list only. Do not invent ratings, notes, dishes or
 * links; leave optional fields out when Kushal has not supplied them. The menu
 * omits anything that is missing. No "last updated" date is shown on the site.
 */
export interface Restaurant {
  id: string;
  name: string;
  city: string;
  /** Kushal's own rating, only when supplied. */
  rating?: number;
  /** Short note or favourite dish, only when supplied. */
  note?: string;
  /** Restaurant link, only when supplied. */
  url?: string;
}

const entries: readonly Restaurant[] = [{ id: 'kasama', name: 'Kasama', city: 'Chicago' }];

/** Only safe web links are shown; anything else is dropped rather than shown broken. */
export const safeUrl = (url: string | undefined) => (url && /^https:\/\/\S+$/.test(url) ? url : undefined);

/**
 * Development only: `?fixture=food` on the dev server appends placeholder
 * entries to exercise ratings, notes and links. They are clearly labelled,
 * never part of a production build, and not real recommendations.
 */
function withDevFixture(list: readonly Restaurant[]): readonly Restaurant[] {
  if (!import.meta.env.DEV || new URLSearchParams(window.location.search).get('fixture') !== 'food') return list;
  return [
    ...list,
    { id: 'fixture-1', name: 'Layout fixture A (not a real restaurant)', city: 'Nowhere', rating: 8.5, note: 'Placeholder note used only to test the layout.', url: 'https://example.com/' },
    { id: 'fixture-2', name: 'Layout fixture B (not a real restaurant)', city: 'Nowhere', note: 'Placeholder with a note and no rating.' },
    { id: 'fixture-3', name: 'Layout fixture C (not a real restaurant)', city: 'A city with a deliberately long name', rating: 10, url: 'javascript:alert(1)' },
  ];
}

export const restaurants: readonly Restaurant[] = withDevFixture(entries);

/** "Find me on Beli" profile link. Pending from Kushal; the action is omitted while undefined. */
export const beliProfileUrl: string | undefined = safeUrl(undefined);
