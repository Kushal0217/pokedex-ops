import { SceneDialog } from '../../shared/ui/SceneDialog';
import './facts.css';
import { facts } from './facts';

/** Plain, readable resume/contact view. No map art or animation; reachable from every screen. */
export function FactsDialog({ open, onOpenChange, onReturnFocus }: { open: boolean; onOpenChange: (open: boolean) => void; onReturnFocus?: () => void }) {
  return (
    <SceneDialog
      open={open}
      onOpenChange={onOpenChange}
      title="Just the facts"
      description="Kushal Gaddam's role, resume and contact links."
      closeLabel="Close"
      tone="plain"
      size="narrow"
      onReturnFocus={onReturnFocus}
    >
      <div className="facts">
        <p className="facts__name">{facts.name}</p>
        <p className="facts__role">{facts.role}</p>

        <div className="facts__resume">
          <a className="facts__button" href={facts.resumeHref} download={facts.resumeFileName}>
            Download resume (PDF)
          </a>
          <a className="facts__link" href={facts.resumeHref} target="_blank" rel="noreferrer">
            Open resume in a new tab
          </a>
        </div>

        <dl className="facts__list">
          {facts.contacts.map((c) => (
            <div key={c.label} className="facts__row">
              <dt>{c.label}</dt>
              <dd>
                <a href={c.href} {...(c.href.startsWith('http') ? { target: '_blank', rel: 'noreferrer' } : {})}>
                  {c.text}
                </a>
              </dd>
            </div>
          ))}
        </dl>
      </div>
    </SceneDialog>
  );
}
