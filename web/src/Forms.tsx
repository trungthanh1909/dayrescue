import { useEffect, useId, useRef, useState, type FormEvent, type ReactNode } from 'react';
import { uid, minutes, type Activity, type Interruption, type Priority } from './state';

function useDraftGuard(dirty: boolean) {
  useEffect(() => {
    if (!dirty) return;
    const guard = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ''; };
    window.addEventListener('beforeunload', guard);
    return () => window.removeEventListener('beforeunload', guard);
  }, [dirty]);
}

export function Modal({ title, children, close }: { title: string; children: ReactNode; close: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const id = useId();
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const overflow = document.body.style.overflow;
    const node = dialog.current!;
    node.showModal(); document.body.style.overflow = 'hidden';
    return () => { node.close(); document.body.style.overflow = overflow; if (previous?.isConnected) previous.focus(); else document.getElementById('main')?.focus(); };
  }, []);
  return <dialog ref={dialog} aria-labelledby={id} onCancel={e => { e.preventDefault(); close(); }}>
    <div className="modal-heading"><h2 id={id}>{title}</h2><button type="button" className="icon-button" aria-label="Close dialog" onClick={close}>×</button></div>{children}
  </dialog>;
}

export function ActivityForm({ date, activity, close, save, remove }: { date: string; activity?: Activity; close: () => void; save: (date: string, activity: Activity) => string | undefined; remove?: () => void }) {
  const [name, setName] = useState(activity?.title ?? '');
  const [duration, setDuration] = useState(activity?.duration ?? 60);
  const [priority, setPriority] = useState<Priority>(activity?.priority ?? 'medium');
  const [fixed, setFixed] = useState(activity?.fixed ?? false);
  const [shorten, setShorten] = useState(activity?.minimum != null);
  const [minimum, setMinimum] = useState(activity?.minimum ?? 30);
  const [error, setError] = useState('');
  const [dirty, setDirty] = useState(false);
  useDraftGuard(dirty);
  function dismiss() { if (!dirty || window.confirm('Discard the unfinished activity changes?')) close(); }
  function submit(e: FormEvent) {
    e.preventDefault();
    // Native date/time editors and autofill can change DOM values before React's
    // change event. Save the form the user actually reviewed, never an older value.
    const fields = new FormData(e.currentTarget as HTMLFormElement);
    const title = String(fields.get('activityName') ?? '').trim();
    const target = String(fields.get('plannedDate')), at = String(fields.get('startTime'));
    const length = Number(fields.get('duration')), isFixed = fields.get('flexibility') === 'fixed';
    const min = !isFixed && fields.has('shortening') ? Number(fields.get('minimumDuration')) : null;
    if (!title || !Number.isInteger(length) || length < 1 || minutes(at) + length > 1440 || (min !== null && (!Number.isInteger(min) || min < 1 || min > length))) { setError('Use a name, a whole-minute duration within this day, and a shortening minimum no longer than the activity.'); return; }
    const value: Activity = { id: activity?.id ?? uid(), title, start: at, duration: length, priority: fields.get('priority') as Priority, fixed: isFixed, minimum: min, status: activity?.status === 'completed' ? 'completed' : 'pending' };
    const failure = save(target, value); if (failure) setError(failure); else close();
  }
  return <Modal title={activity ? 'Edit activity' : 'Make room for an activity'} close={dismiss}>
    <p className="helper">Fixed keeps its time and duration. Flexible can move; shortening needs your permission.</p>
    <form onSubmit={submit} onChange={() => { setDirty(true); setError(''); }} autoComplete="off">
      <label htmlFor="activity-name">Activity name</label><input id="activity-name" name="activityName" value={name} onChange={e => setName(e.target.value)} maxLength={120} placeholder="e.g. Study Python…" required />
      <div className="form-row"><div><label htmlFor="activity-date">Planned date</label><input id="activity-date" name="plannedDate" type="date" defaultValue={date} required /></div><div><label htmlFor="activity-time">Starts at</label><input id="activity-time" name="startTime" type="time" defaultValue={activity?.start ?? '09:00'} required /></div></div>
      <div className="form-row"><div><label htmlFor="activity-duration">Duration (minutes)</label><input id="activity-duration" name="duration" type="number" inputMode="numeric" min="1" max="1440" value={Number.isFinite(duration) ? duration : ''} onChange={e => setDuration(e.target.valueAsNumber)} required /></div><div><label htmlFor="activity-priority">Priority</label><select id="activity-priority" name="priority" value={priority} onChange={e => setPriority(e.target.value as Priority)}><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option></select></div></div>
      <label htmlFor="activity-flexibility">How flexible?</label><select id="activity-flexibility" name="flexibility" value={fixed ? 'fixed' : 'flexible'} onChange={e => { setFixed(e.target.value === 'fixed'); if (e.target.value === 'fixed') setShorten(false); }}><option value="flexible">Flexible — can move</option><option value="fixed">Fixed — keeps its time</option></select>
      {!fixed && <label className="check-label"><input name="shortening" type="checkbox" checked={shorten} onChange={e => setShorten(e.target.checked)} /> Allow shortening</label>}
      {!fixed && shorten && <><label htmlFor="activity-minimum">Minimum duration (minutes)</label><input id="activity-minimum" name="minimumDuration" type="number" min="1" max={duration} value={Number.isFinite(minimum) ? minimum : ''} onChange={e => setMinimum(e.target.valueAsNumber)} required /></>}
      {error && <p className="error" role="alert">{error}</p>}
      <div className="modal-actions">{remove && <button type="button" className="text-button danger" onClick={() => { if (window.confirm(`Remove “${activity!.title}” from this browser's plan?`)) { remove(); close(); } }}>Remove activity</button>}<button type="button" className="button secondary" onClick={dismiss}>Cancel</button><button className="button primary" type="submit">{activity?.status === 'unscheduled' ? 'Save & schedule' : 'Save activity'}</button></div>
    </form>
  </Modal>;
}

export function InterruptionForm({ date, event, close, save, remove }: { date: string; event?: Interruption; close: () => void; save: (date: string, value: Interruption) => string | undefined; remove?: () => void }) {
  const [name, setName] = useState(event?.title ?? '');
  const [unavoidable, setUnavoidable] = useState(true); const [error, setError] = useState(''); const [dirty, setDirty] = useState(false);
  useDraftGuard(dirty);
  const dismiss = () => { if (!dirty || window.confirm('Discard the unfinished interruption?')) close(); };
  function submit(e: FormEvent) {
    e.preventDefault();
    const fields = new FormData(e.currentTarget as HTMLFormElement);
    const title = String(fields.get('eventName') ?? '').trim(), at = String(fields.get('eventStart')), until = String(fields.get('eventEnd'));
    if (!title || minutes(until) <= minutes(at) || !fields.has('unavoidable')) { setError('Add a name and a later end time. Interruptions must be unavoidable busy time within one day.'); return; }
    const failure = save(String(fields.get('eventDate')), { id: event?.id ?? uid(), title, start: at, end: until }); if (failure) setError(failure); else close();
  }
  return <Modal title="What changed?" close={dismiss}><p className="helper">Add the time that is no longer available. Fixed commitments stay fixed until you explicitly edit them.</p>
    <form onSubmit={submit} autoComplete="off" onChange={() => { setDirty(true); setError(''); }}>
      <label htmlFor="event-name">What came up?</label><input id="event-name" name="eventName" value={name} onChange={e => setName(e.target.value)} maxLength={120} placeholder="e.g. An unexpected appointment…" required />
      <label htmlFor="event-date">Date</label><input id="event-date" name="eventDate" type="date" defaultValue={date} required />
      <div className="form-row"><div><label htmlFor="event-start">Starts at</label><input id="event-start" name="eventStart" type="time" defaultValue={event?.start ?? '13:00'} required /></div><div><label htmlFor="event-end">Ends at</label><input id="event-end" name="eventEnd" type="time" defaultValue={event?.end ?? '14:00'} required /></div></div>
      <label className="check-label"><input name="unavoidable" type="checkbox" checked={unavoidable} onChange={e => setUnavoidable(e.target.checked)} /> This is unavoidable busy time</label>
      {!unavoidable && <p className="helper">Movable interruptions are not supported. Leave this checked to reserve the time.</p>}
      {error && <p className="error" role="alert">{error}</p>}
      <div className="modal-actions">{remove && <button type="button" className="text-button danger" onClick={() => { if (window.confirm('Remove this interruption?')) { remove(); close(); } }}>Remove</button>}<button type="button" className="button secondary" onClick={dismiss}>Cancel</button><button className="button primary" type="submit">Save interruption</button></div>
    </form>
  </Modal>;
}
