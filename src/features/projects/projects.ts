/**
 * Personal projects: the single ordered source for both the Badges tab and the
 * All projects tab. To add a project, add one entry here (and optionally a
 * badge design in Badge.tsx). Nothing else needs to change.
 *
 * Rules: only real, approved projects. Never invent a URL, metric or status;
 * leave `links` empty and `status` out when they are not supplied. Workplace
 * achievements stay in the resume, not here.
 */
export type ProjectLinkKind = 'demo' | 'source' | 'writeup';

export const LINK_LABEL: Record<ProjectLinkKind, string> = {
  demo: 'Live demo',
  source: 'Source code',
  writeup: 'Read more',
};

export interface ProjectLink {
  kind: ProjectLinkKind;
  url: string;
}

export interface Project {
  /** Stable ID, also used in the page address. */
  id: string;
  name: string;
  /** Short name shown under the badge. */
  shortName: string;
  blurb: string;
  /** Optional longer text for the badge detail panel. */
  description?: string;
  /** Shown only when approved, e.g. "In progress". */
  status?: string;
  /** Badge design key from Badge.tsx; the default badge is used when missing. */
  badge?: string;
  /** Available links only. A project may have several, or none. */
  links: readonly ProjectLink[];
  /** Display order, lowest first. */
  order: number;
}

const entries: readonly Project[] = [
  {
    id: 'pokedex-ops',
    name: 'Pokédex Ops Skill',
    shortName: 'Pokédex Ops',
    blurb:
      'An eval-driven MCP server and Agent Skill for PostgreSQL/Aurora operations, using Pokémon data to explore query analysis, index proposals, health checks, and guarded index changes.',
    status: 'In progress',
    badge: 'pokedex-ops',
    // Repository, demo and write-up URLs are pending from Kushal.
    links: [],
    order: 1,
  },
];

const byOrder = (list: readonly Project[]) => [...list].sort((a, b) => a.order - b.order);

/** Only safe web links become buttons; anything else is dropped rather than shown broken. */
export const validLinks = (project: Project) => project.links.filter((link) => /^https:\/\/\S+$/.test(link.url));

export const projects: readonly Project[] = byOrder(entries);

/**
 * Development only: `?fixture=projects` on the dev server appends placeholder
 * entries to exercise a case with more than eight badges. They are clearly
 * labelled, never part of a production build, and not real projects.
 */
export function withDevFixture(list: readonly Project[]): readonly Project[] {
  if (!import.meta.env.DEV || new URLSearchParams(window.location.search).get('fixture') !== 'projects') return list;
  const samples: Project[] = Array.from({ length: 10 }, (_, i) => ({
    id: `fixture-${i + 1}`,
    name: `Layout fixture ${i + 1} (not a real project)`,
    shortName: `Fixture ${i + 1}`,
    blurb: 'Placeholder entry used only to test the layout with many badges. It is not a real project and never ships.',
    links: i % 3 === 0 ? [{ kind: 'source' as const, url: 'https://example.com/' }, { kind: 'demo' as const, url: 'https://example.com/' }] : [],
    order: 100 + i,
  }));
  return byOrder([...list, ...samples]);
}
