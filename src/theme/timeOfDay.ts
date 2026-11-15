/** The three lighting treatments. All share the same artwork; only tokens change. */
export const TIME_MODES = ['day', 'evening', 'night'] as const;
export type TimeMode = (typeof TIME_MODES)[number];

export const TIME_MODE_LABEL: Record<TimeMode, string> = {
  day: 'Day',
  evening: 'Evening',
  night: 'Night',
};

/** Applies a lighting mode to the whole document via the `data-time` attribute. */
export function applyTimeMode(mode: TimeMode): void {
  document.documentElement.dataset.time = mode;
}
