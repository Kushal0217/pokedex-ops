import { LIGHTING_PREFERENCES, PREFERENCE_LABEL, type LightingPreference, type TimeMode } from '../../theme/timeOfDay';

/** Auto / Day / Evening / Night. Native radios, so arrow keys and touch work as expected. */
export function LightingSelector({ value, mode, onChange }: { value: LightingPreference; mode: TimeMode; onChange: (next: LightingPreference) => void }) {
  return (
    <fieldset className="lighting">
      <legend className="lighting__legend">
        Lighting
        {value === 'auto' && <span className="lighting__now"> · Auto is showing {PREFERENCE_LABEL[mode].toLowerCase()} for your local time</span>}
      </legend>
      <div className="lighting__options">
        {LIGHTING_PREFERENCES.map((option) => (
          <label key={option} className="lighting__option">
            <input type="radio" name="lighting" value={option} checked={value === option} onChange={() => onChange(option)} />
            <span>{PREFERENCE_LABEL[option]}</span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}
