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

export const restaurants: readonly Restaurant[] = [{ id: 'kasama', name: 'Kasama', city: 'Chicago' }];

/** "Find me on Beli" profile link. Pending from Kushal; the action is omitted while undefined. */
export const beliProfileUrl: string | undefined = undefined;
