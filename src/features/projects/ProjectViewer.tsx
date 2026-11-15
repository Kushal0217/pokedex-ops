import * as Tabs from '@radix-ui/react-tabs';
import { useState } from 'react';
import { SceneDialog } from '../../shared/ui/SceneDialog';
import { Badge, BadgeCaseIcon } from './Badge';
import './projects.css';
import { LINK_LABEL, validLinks, type Project } from './projects';

export type ProjectTab = 'badges' | 'list';

interface Props {
  /** Which tab is showing, or null when the viewer is closed. */
  tab: ProjectTab | null;
  onTabChange: (tab: ProjectTab | null) => void;
  projects: readonly Project[];
  actions?: React.ReactNode;
  onReturnFocus: () => void;
}

function ProjectLinks({ project }: { project: Project }) {
  const links = validLinks(project);
  if (links.length === 0) return null;
  return (
    <ul className="project-links" aria-label={`${project.name} links`}>
      {links.map((link) => (
        <li key={`${link.kind}-${link.url}`}>
          <a href={link.url} target="_blank" rel="noreferrer">
            {LINK_LABEL[link.kind]}
          </a>
        </li>
      ))}
    </ul>
  );
}

/**
 * The badge case. Two tabs over one project list: Badges (collectible view
 * with a detail panel) and All projects (every blurb and link readable at
 * once). No badge is locked and nothing here depends on gameplay.
 */
export function ProjectViewer({ tab, onTabChange, projects, actions, onReturnFocus }: Props) {
  const [selectedId, setSelectedId] = useState(projects[0]?.id);
  const selected = projects.find((p) => p.id === selectedId) ?? projects[0];

  return (
    <SceneDialog
      open={tab !== null}
      onOpenChange={(open) => !open && onTabChange(null)}
      title="Badge case"
      description="Kushal's personal projects, as badges or as one readable list."
      closeLabel="Back to town"
      mark={<BadgeCaseIcon className="projects__mark" />}
      actions={actions}
      onReturnFocus={onReturnFocus}
    >
      <Tabs.Root className="projects" value={tab ?? 'badges'} onValueChange={(value) => onTabChange(value as ProjectTab)}>
        <Tabs.List className="projects__tabs" aria-label="Project views">
          <Tabs.Trigger className="projects__tab" value="badges">
            Badges
          </Tabs.Trigger>
          <Tabs.Trigger className="projects__tab" value="list">
            All projects
          </Tabs.Trigger>
        </Tabs.List>

        <Tabs.Content className="projects__panel" value="badges">
          <p className="projects__hint">Pick a badge to read about the project. Every project is also in “All projects”.</p>
          <ul className="badge-grid">
            {projects.map((project) => (
              <li key={project.id}>
                <button
                  type="button"
                  className="badge-button"
                  aria-pressed={project.id === selected?.id}
                  onClick={() => setSelectedId(project.id)}
                >
                  <Badge design={project.badge} className="badge-button__art" />
                  <span className="badge-button__name">{project.shortName}</span>
                </button>
              </li>
            ))}
          </ul>

          {selected && (
            <section className="project-detail" aria-live="polite" aria-labelledby="project-detail-name">
              <Badge design={selected.badge} className="project-detail__art" />
              <div className="project-detail__text">
                <h3 id="project-detail-name" className="project-name">
                  {selected.name}
                  {selected.status && <span className="project-status">{selected.status}</span>}
                </h3>
                <p>{selected.description ?? selected.blurb}</p>
                <ProjectLinks project={selected} />
              </div>
            </section>
          )}
        </Tabs.Content>

        <Tabs.Content className="projects__panel" value="list">
          <ol className="project-list">
            {projects.map((project) => (
              <li key={project.id} className="project-list__item">
                <Badge design={project.badge} className="project-list__art" />
                <div>
                  <h3 className="project-name">
                    {project.name}
                    {project.status && <span className="project-status">{project.status}</span>}
                  </h3>
                  <p>{project.blurb}</p>
                  <ProjectLinks project={project} />
                </div>
              </li>
            ))}
          </ol>
        </Tabs.Content>
      </Tabs.Root>
    </SceneDialog>
  );
}
