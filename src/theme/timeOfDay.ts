import { useCallback, useEffect, useState } from 'react';

/**
 * World lighting. Auto follows the visitor's device clock only: no geolocation,
 * no IP lookup, no time or weather service, and nothing is sent anywhere.
 * All three modes share the same artwork; only theme tokens change.
 *
 * Keep the hour ranges and storage key in step with the inline script in
 * index.html, which applies the mode before first paint.
 */
export const TIME_MODES = ['day', 'evening', 'night'] as const;
export type TimeMode = (typeof TIME_MODES)[number];
export const LIGHTING_PREFERENCES = ['auto', ...TIME_MODES] as const;
export type LightingPreference = (typeof LIGHTING_PREFERENCES)[number];

export const PREFERENCE_LABEL: Record<LightingPreference, string> = {
  auto: 'Auto',
  day: 'Day',
  evening: 'Evening',
  night: 'Night',
};

export const STORAGE_KEY = 'lighting';
/** Local hours at which Auto changes mode. */
const BOUNDARY_HOURS = [7, 17, 20] as const;

/** Day 07:00-16:59, Evening 17:00-19:59, Night 20:00-06:59 (device-local). */
export function modeForHour(hour: number): TimeMode {
  if (hour >= 7 && hour < 17) return 'day';
  if (hour >= 17 && hour < 20) return 'evening';
  return 'night';
}

export function resolveMode(preference: LightingPreference, now: Date): TimeMode {
  return preference === 'auto' ? modeForHour(now.getHours()) : preference;
}

/** Milliseconds until Auto next changes mode. */
export function msUntilNextBoundary(now: Date): number {
  const candidates = BOUNDARY_HOURS.flatMap((hour) => [0, 1].map((dayOffset) => {
    const at = new Date(now);
    at.setDate(now.getDate() + dayOffset);
    at.setHours(hour, 0, 0, 0);
    return at.getTime() - now.getTime();
  }));
  return Math.min(...candidates.filter((ms) => ms > 0));
}

const isPreference = (value: unknown): value is LightingPreference =>
  typeof value === 'string' && (LIGHTING_PREFERENCES as readonly string[]).includes(value);

/** Saved choice, or Auto. Storage may be unavailable (private mode, blocked): that is fine. */
export function readPreference(): LightingPreference {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    return isPreference(stored) ? stored : 'auto';
  } catch {
    return 'auto';
  }
}

function writePreference(preference: LightingPreference): void {
  try {
    if (preference === 'auto') window.localStorage.removeItem(STORAGE_KEY);
    else window.localStorage.setItem(STORAGE_KEY, preference);
  } catch {
    // The selector still works for this visit.
  }
}

function apply(mode: TimeMode): void {
  if (document.documentElement.dataset.time !== mode) document.documentElement.dataset.time = mode;
}

/**
 * Lighting preference plus the mode it currently resolves to.
 * Auto is re-evaluated when the page becomes visible or focused again (which
 * also picks up a changed device clock or timezone) and by one timer set for
 * the next boundary. There is no polling loop.
 */
export function useLighting() {
  const [preference, setPreferenceState] = useState<LightingPreference>(readPreference);
  const [mode, setMode] = useState<TimeMode>(() => resolveMode(readPreference(), new Date()));

  const setPreference = useCallback((next: LightingPreference) => {
    writePreference(next);
    setPreferenceState(next);
  }, []);

  useEffect(() => {
    let timer = 0;
    const refresh = () => {
      const next = resolveMode(preference, new Date());
      apply(next);
      setMode(next);
      window.clearTimeout(timer);
      if (preference === 'auto') timer = window.setTimeout(refresh, msUntilNextBoundary(new Date()) + 500);
    };
    const onVisible = () => {
      if (document.visibilityState === 'visible') refresh();
    };
    refresh();
    document.addEventListener('visibilitychange', onVisible);
    window.addEventListener('focus', refresh);
    window.addEventListener('pageshow', refresh);
    return () => {
      window.clearTimeout(timer);
      document.removeEventListener('visibilitychange', onVisible);
      window.removeEventListener('focus', refresh);
      window.removeEventListener('pageshow', refresh);
    };
  }, [preference]);

  return { preference, mode, setPreference };
}
