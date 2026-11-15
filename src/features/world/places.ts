/**
 * Map places as content. The town grows by adding entries here (Slice 3);
 * custom artwork or interaction code per place is optional.
 */
export interface Place {
  id: string;
  /** Visible label on the map. */
  label: string;
  /** Short hint shown beside the label. */
  hint: string;
  category: string;
}

export const ramenShop: Place = { id: 'ramen', label: 'Ramen shop', hint: 'go inside', category: 'Food' };
