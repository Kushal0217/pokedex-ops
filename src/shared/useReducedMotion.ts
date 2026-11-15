import { useMediaQuery } from './useMediaQuery';

/** Tracks the operating system's reduced-motion preference. */
export function useReducedMotion(): boolean {
  return useMediaQuery('(prefers-reduced-motion: reduce)');
}
