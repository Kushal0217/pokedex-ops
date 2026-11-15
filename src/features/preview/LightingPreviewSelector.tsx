import { TIME_MODES, TIME_MODE_LABEL, type TimeMode } from '../../theme/timeOfDay';

/**
 * TEMPORARY (Slice 1): manual lighting preview for art review.
 * Slice 3 replaces this with the production Auto / Day / Evening / Night control.
 */
export function LightingPreviewSelector({ value, onChange }: { value: TimeMode; onChange: (mode: TimeMode) => void }) {
  return (
    <fieldset className="lighting">
      <legend className="lighting__legend">Lighting preview</legend>
      <div className="lighting__options">
        {TIME_MODES.map((mode) => (
          <label key={mode} className="lighting__option">
            <input
              type="radio"
              name="lighting-preview"
              value={mode}
              checked={value === mode}
              onChange={() => onChange(mode)}
            />
            <span>{TIME_MODE_LABEL[mode]}</span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}
