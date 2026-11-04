const hours = Array.from({ length: 24 }, (_, i) => String(i).padStart(2, '0'));
const minutes = Array.from({ length: 60 }, (_, i) => String(i).padStart(2, '0'));

// Uncontrolled native selects retain the actual values reviewed by the user,
// including autofill/native edits that precede a React change event.
export function TimePicker({ id, name, label, defaultValue }: { id: string; name: string; label: string; defaultValue: string }) {
  return <fieldset className="time-picker" id={id}>
    <legend>{label} <span className="time-format">24-hour</span></legend>
    <div className="time-parts">
      <div><label htmlFor={`${id}-hour`}>Hour</label><select id={`${id}-hour`} name={`${name}Hour`} aria-label={`${label} hour`} defaultValue={defaultValue.slice(0, 2)} required>{hours.map(hour => <option key={hour}>{hour}</option>)}</select></div>
      <span className="time-colon" aria-hidden="true">:</span>
      <div><label htmlFor={`${id}-minute`}>Minute</label><select id={`${id}-minute`} name={`${name}Minute`} aria-label={`${label} minute`} defaultValue={defaultValue.slice(3)} required>{minutes.map(minute => <option key={minute}>{minute}</option>)}</select></div>
    </div>
  </fieldset>;
}

export function formTime(fields: FormData, name: string) {
  return `${fields.get(`${name}Hour`)}:${fields.get(`${name}Minute`)}`;
}
