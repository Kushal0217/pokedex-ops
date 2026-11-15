import { facts } from '../facts/facts';
import '../places.css';
import { profile } from './profile';

/** Work / profile: a short introduction and the resume. No achievement metrics or case studies. */
export function ProfilePanel({ onOpenFacts }: { onOpenFacts: () => void }) {
  return (
    <div className="place-panel">
      <p className="place-panel__kicker">{profile.role}</p>
      {profile.lines.map((line) => (
        <p key={line}>{line}</p>
      ))}
      <div className="place-panel__actions">
        <a className="place-panel__button" href={facts.resumeHref} download={facts.resumeFileName}>
          Download resume (PDF)
        </a>
        <button type="button" className="place-panel__button place-panel__button--quiet" onClick={onOpenFacts}>
          Contact details
        </button>
      </div>
    </div>
  );
}
