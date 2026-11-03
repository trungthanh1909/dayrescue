import { useEffect, useRef, useState } from 'react';
import { ActivityForm, InterruptionForm, Modal } from './Forms';
import { apiCall, preflight, type Preflight, type Proposal } from './api';
import { STORAGE_KEY, affected, applyPlan, changeDay, clock, dateLabel, dayInput, emptyDay, emptyStore, loadStore, localClock, localDate, minutes, moveDate, parseStore, saveStore, signature, uid, undoPlan, validDate, weekDates, type Activity, type Day, type Interruption, type Store } from './state';

type Review = { date: string; signature: string; response: Proposal; checkedAt: string };
type Editor = { type: 'activity'; date: string; value?: Activity } | { type: 'event'; date: string; value?: Interruption } | null;
const initialDate = () => { const value = new URLSearchParams(location.search).get('date'); return value && validDate(value) ? value : localDate(); };
const errorMessage = (e: unknown) => e instanceof Error ? e.message : 'The request could not be completed. Your plan is unchanged.';

function ActivityCard({ activity: a, dayDate, now, edit, complete, change }: { activity: Activity; dayDate: string; now: Date; edit?: () => void; complete?: () => void; change?: string }) {
  const today = dayDate === localDate(now); const minute = minutes(localClock(now));
  const current = today && a.status === 'pending' && minutes(a.start) <= minute && minute < minutes(a.start) + a.duration;
  const elapsed = today && a.status === 'pending' && minutes(a.start) + a.duration <= minute;
  return <li className={`activity ${a.fixed ? 'fixed-card' : ''} ${a.status === 'completed' ? 'completed' : ''} ${change?.startsWith('Moved') || change?.includes('Shortened') ? 'adjusted-card' : ''}`}>
    <div className="activity-heading"><div><h3>{a.title}</h3><div className="activity-meta"><span>{a.start}–{clock(minutes(a.start) + a.duration)}</span><span>{a.duration} min</span><span>{a.priority} priority</span></div></div><span className={`badge ${a.fixed ? 'fixed' : 'flexible'}`}>{a.fixed ? 'Fixed' : 'Flexible'}</span></div>
    <p className="permission">{a.minimum !== null && !a.fixed ? `May shorten to ${a.minimum} min` : 'Shortening not allowed'}</p>
    {change && <p className="change">{change}</p>}
    {current && <span className="badge current">Happening now</span>}{elapsed && <span className="helper">Elapsed · Still pending</span>}
    {a.status === 'completed' && <span className="badge fixed">Completed by you</span>}
    {(edit || complete) && <div className="activity-actions">{complete && <label className="completion"><input type="checkbox" checked={a.status === 'completed'} onChange={complete} aria-label={`Mark ${a.title} ${a.status === 'completed' ? 'pending' : 'completed'}`} /> Done</label>}{edit && <button className="text-button" onClick={edit} aria-label={`Edit ${a.title}`}>Edit</button>}</div>}
  </li>;
}

export default function App() {
  const [loaded] = useState(() => { try { return loadStore(localStorage); } catch { return { store: emptyStore(), error: 'Browser storage is unavailable. Reset to continue in this tab.', blocked: true }; } });
  const [store, setStore] = useState<Store>(loaded.store); const storeRef = useRef(store); const persisted = useRef(store.writeId);
  const [blocked, setBlocked] = useState(loaded.blocked); const [storageError, setStorageError] = useState(loaded.error);
  const [selected, setSelected] = useState(initialDate); const selectedRef = useRef(selected);
  const [view, setView] = useState(location.hash === '#week' ? 'week' : 'day');
  const [now, setNow] = useState(() => new Date()); const [editor, setEditor] = useState<Editor>(null);
  const [health, setHealth] = useState<{ live_enabled: boolean; evidence?: string } | null>(null); const [serviceError, setServiceError] = useState('');
  const [notice, setNotice] = useState(''); const [check, setCheck] = useState<Preflight | null>(null);
  const [review, setReview] = useState<Review | null>(null); const [busy, setBusy] = useState(false); const busyRef = useRef(false);
  const [applying, setApplying] = useState(false); const [confirmApply, setConfirmApply] = useState(false); const requestToken = useRef(0);
  const day = store.days[selected] ?? emptyDay();
  const pending = day.activities.filter(a => a.status === 'pending').sort((a,b) => minutes(a.start)-minutes(b.start));
  const current = pending.find(a => selected === localDate(now) && minutes(a.start) <= minutes(localClock(now)) && minutes(localClock(now)) < minutes(a.start) + a.duration);
  const next = [...pending].sort((a,b) => minutes(a.start)-minutes(b.start)).find(a => selected > localDate(now) || (selected === localDate(now) && minutes(a.start) > minutes(localClock(now))));
  const activeReview = review && review.date === selected && review.signature === signature(selected, day) ? review : null;

  function invalidate() { requestToken.current++; setReview(null); setCheck(null); setConfirmApply(false); }
  function chooseDate(date: string) { if (!validDate(date)) return; selectedRef.current = date; setSelected(date); invalidate(); }
  function commit(days: Store['days']): boolean {
    if (blocked) { setNotice('Reset the unreadable browser storage explicitly before saving a new plan.'); return false; }
    try {
      const latest = loadStore(localStorage);
      if (latest.blocked) { setBlocked(true); setStorageError(latest.error); invalidate(); return false; }
      if (latest.store.writeId !== persisted.current) { storeRef.current = latest.store; setStore(latest.store); persisted.current = latest.store.writeId; setEditor(null); invalidate(); setNotice('Another tab changed the plan. The latest plans are loaded; repeat your edit to avoid overwriting them.'); return false; }
    } catch { /* Storage can be unavailable; retain edits in memory and report it below. */ }
    const nextStore: Store = { version: 1, writeId: uid(), days };
    try { saveStore(localStorage, nextStore); persisted.current = nextStore.writeId; setStorageError(''); }
    catch { setStorageError('Browser storage is unavailable or full. Changes are in this tab only and may be lost on reload.'); }
    storeRef.current = nextStore; setStore(nextStore); invalidate(); return true;
  }
  function update(date: string, value: Day) { return commit({ ...storeRef.current.days, [date]: value }); }
  function getDay(date: string) { return storeRef.current.days[date] ?? emptyDay(); }
  function saveActivity(target: string, value: Activity): string | undefined {
    if (!validDate(target) || !editor) return 'Choose a valid planned date.';
    const days = { ...storeRef.current.days }; const source = getDay(editor.date);
    const destination = target === editor.date ? source : getDay(target);
    const list = destination.activities.filter(a => a.id !== value.id);
    if (list.length >= 8) return 'A day supports up to 8 activities. Choose another date or remove one first.';
    if (target !== editor.date && editor.value) days[editor.date] = changeDay(source, { activities: source.activities.filter(a => a.id !== value.id) });
    days[target] = changeDay(destination, { activities: [...list, value] });
    if (!commit(days)) return 'The edit was not saved. Review the storage message.';
    chooseDate(target); setView('day'); setNotice('Activity saved in this browser.'); return undefined;
  }
  function saveEvent(target: string, value: Interruption): string | undefined {
    if (!validDate(target) || !editor) return 'Choose a valid date.';
    const days = { ...storeRef.current.days }; const source = getDay(editor.date); const destination = target === editor.date ? source : getDay(target);
    const list = destination.interruptions.filter(b => b.id !== value.id);
    if (list.length >= 10) return 'A day supports up to 10 interruptions.';
    if (target !== editor.date && editor.value) days[editor.date] = changeDay(source, { interruptions: source.interruptions.filter(b => b.id !== value.id) });
    days[target] = changeDay(destination, { interruptions: [...list, value] });
    if (!commit(days)) return 'The interruption was not saved. Review the storage message.';
    chooseDate(target); setView('day'); setNotice('Interruption added. Review the affected activities before rescue.'); return undefined;
  }
  function sample() {
    const target = selected <= localDate() ? moveDate(localDate(), 1) : selected;
    const existing = getDay(target);
    if (existing.activities.length || existing.interruptions.length) { setNotice('Choose an empty future day for the sample. Your existing plan was not replaced.'); return; }
    const base = { priority: 'medium' as const, fixed: false, minimum: null, status: 'pending' as const };
    if (update(target, changeDay(existing, { demo: true, activities: [
      { ...base, id: uid(), title: 'Study Python', start: '09:00', duration: 90, priority: 'high' },
      { ...base, id: uid(), title: 'Team check-in', start: '10:30', duration: 30, fixed: true, priority: 'high' },
      { ...base, id: uid(), title: 'Go for a run', start: '16:00', duration: 60, minimum: 30 },
    ] }))) { chooseDate(target); setNotice(`Hand-authored sample activities added for ${dateLabel(target)}. Demo data, not AI output.`); }
  }
  async function checkOrRescue(generate: boolean) {
    if (busyRef.current || (generate && !health?.live_enabled)) return;
    const date = selectedRef.current; const snapshot = structuredClone(getDay(date)); const sig = signature(date, snapshot); const token = ++requestToken.current;
    setServiceError(''); setCheck(null); setReview(null); busyRef.current = true; setBusy(true);
    try {
      const input = dayInput(date, snapshot); const checked = await preflight(input);
      if (token !== requestToken.current || selectedRef.current !== date || signature(date, getDay(date)) !== sig) { setNotice('Inputs changed. The old check was discarded.'); return; }
      setCheck(checked);
      if (!generate || checked.conflicts.length) return;
      const response = await apiCall<Proposal>('/rescue', { day: input, request_id: uid() });
      if (token !== requestToken.current || selectedRef.current !== date || signature(date, getDay(date)) !== sig) { setNotice('Inputs changed while rescue was running. The proposal was discarded.'); return; }
      if (response.fingerprint !== checked.fingerprint) throw new Error('The response does not match the current day. No plan was applied.');
      setReview({ date, signature: sig, response, checkedAt: input.now });
    } catch (e) { if (token === requestToken.current) setServiceError(errorMessage(e)); }
    finally { busyRef.current = false; setBusy(false); }
  }
  async function accept() {
    if (!activeReview?.response.plan || !activeReview.response.validation?.valid || applying) return;
    const captured = activeReview; setApplying(true); setServiceError('');
    try {
      const freshDay = getDay(captured.date);
      if (selectedRef.current !== captured.date || signature(captured.date, freshDay) !== captured.signature) throw new Error('Inputs changed. This proposal is stale.');
      const response = await apiCall<Preflight>('/validate', { day: dayInput(captured.date, freshDay), proposal: captured.response.plan, fingerprint: captured.response.fingerprint });
      if (!response.validation?.valid || response.fingerprint !== captured.response.fingerprint) throw new Error('Python rejected this proposal for the current clock or inputs. No plan was applied.');
      const currentDay = getDay(captured.date);
      if (selectedRef.current !== captured.date || signature(captured.date, currentDay) !== captured.signature) throw new Error('Inputs changed while checking. No plan was applied.');
      const applied = applyPlan(captured.date, currentDay, captured.response.plan!, captured.signature, true);
      if (captured.response.evidence === 'offline_fixture') applied.demo = true;
      if (update(captured.date, applied)) setNotice(captured.response.evidence === 'offline_fixture' ? 'Offline test fixture applied locally. This is demo data, not Muse output. Undo is available.' : 'Revised plan applied in this browser. You can undo this acceptance.');
    } catch (e) { setServiceError(errorMessage(e)); setReview(null); }
    finally { setApplying(false); setConfirmApply(false); }
  }
  function resetStorage() {
    if (!window.confirm('Reset only DayRescue’s browser-local plans? This cannot be undone.')) return;
    const fresh = { ...emptyStore(), writeId: uid() };
    try { saveStore(localStorage, fresh); persisted.current = fresh.writeId; setStorageError(''); }
    catch { persisted.current = ''; setStorageError('Storage remains unavailable. New plans will stay in this tab only.'); }
    setBlocked(false); storeRef.current = fresh; setStore(fresh); invalidate();
  }
  useEffect(() => {
    let live = true;
    apiCall<{ live_enabled: boolean; evidence?: string }>('/health').then(value => { if (live) setHealth({ live_enabled: value.live_enabled === true, evidence: value.evidence }); }).catch(() => { if (live) setHealth(null); });
    const timer = window.setInterval(() => setNow(new Date()), 15000);
    return () => { live = false; window.clearInterval(timer); requestToken.current++; };
  }, []);
  useEffect(() => {
    const listener = (event: StorageEvent) => {
      if (event.key !== STORAGE_KEY) return;
      try { const value = event.newValue ? parseStore(event.newValue) : emptyStore(); storeRef.current = value; persisted.current = value.writeId; setStore(value); setBlocked(false); setStorageError(''); setEditor(null); invalidate(); setNotice('Plans changed in another tab. Any previous proposal was discarded.'); }
      catch { setBlocked(true); setStorageError('Another tab wrote unreadable planner data. It has not been overwritten.'); invalidate(); }
    };
    window.addEventListener('storage', listener); return () => window.removeEventListener('storage', listener);
  }, []);
  useEffect(() => { const url = new URL(location.href); url.searchParams.set('date', selected); url.hash = view; history.replaceState(null, '', url); }, [selected, view]);
  useEffect(() => { const navigate = () => { setView(location.hash === '#week' ? 'week' : 'day'); const value = new URLSearchParams(location.search).get('date'); if (value && validDate(value)) chooseDate(value); }; window.addEventListener('popstate', navigate); return () => window.removeEventListener('popstate', navigate); }, []);

  const sorted = [...day.activities].filter(a => a.status !== 'unscheduled').sort((a,b) => minutes(a.start)-minutes(b.start));
  const postponed = day.activities.filter(a => a.status === 'unscheduled');
  const accepted = activeReview?.response.status === 'valid' && activeReview.response.validation?.valid && activeReview.response.plan;
  return <><a className="skip-link" href="#main">Skip to content</a><div className="app-shell">
    <aside className="sidebar"><a className="brand" href="#day" onClick={() => setView('day')}><img src="/mark.svg" width="40" height="40" alt=""/><span translate="no">DayRescue</span></a><p className="brand-note">A little room for real life.</p>
      <nav aria-label="Main"><a href="#day" aria-current={view === 'day' ? 'page' : undefined} onClick={() => setView('day')}><span aria-hidden="true">☀</span> My day</a><a href="#week" aria-current={view === 'week' ? 'page' : undefined} onClick={() => setView('week')}><span aria-hidden="true">▦</span> My week</a></nav>
      <div className="sidebar-note"><span aria-hidden="true">✳</span><p>Your plans can change.<br/>What matters can stay.</p></div><p className="sidebar-foot">One day at a time.</p>
    </aside><div className="workspace"><div className="storage-banner"><span className="dot" aria-hidden="true"/>Browser-local planning<span>No cloud sync. Keep this browser’s data to keep your plans.</span></div>
    <main id="main" tabIndex={-1}><div className="page-heading"><div><h1>{view === 'week' ? 'My week' : 'My day'}</h1><p>{view === 'week' ? 'A little further ahead. One day at a time.' : 'A plan to start from. Room to change it.'}</p></div><button className="button interruption-button" onClick={() => setEditor({ type: 'event', date: selected })}>↺ Something changed?</button></div>
      {health?.evidence === 'offline_fixture' && <div className="demo-notice" role="status"><strong>Offline integration test</strong><p>Hand-authored MockTransport fixtures. No Meta requests or live Muse output. Browser test data only.</p></div>}
      {storageError && <div className="feedback error" role="alert"><p>{storageError}</p><button className="text-button" onClick={resetStorage}>Reset DayRescue browser storage</button></div>}
      {notice && <div className="feedback notice" role="status"><p>{notice}</p><button className="icon-button" onClick={() => setNotice('')} aria-label="Dismiss message">×</button></div>}
      <div className="date-row"><div className="date-switcher"><button className="icon-button" aria-label="Previous day" onClick={() => chooseDate(moveDate(selected, -1))}>‹</button><div><h2>{dateLabel(selected)}</h2><span className="helper">{selected === localDate(now) ? 'Today' : selected === moveDate(localDate(now), 1) ? 'Tomorrow' : 'Selected day'}</span></div><button className="icon-button" aria-label="Next day" onClick={() => chooseDate(moveDate(selected, 1))}>›</button></div><div className="date-controls"><label className="visually-hidden" htmlFor="selected-date">Selected date</label><input id="selected-date" type="date" value={selected} onChange={e => chooseDate(e.target.value)} onBlur={e => { if (validDate(e.currentTarget.value) && e.currentTarget.value !== selectedRef.current) chooseDate(e.currentTarget.value); else if (!validDate(e.currentTarget.value)) e.currentTarget.value = selectedRef.current; }}/><button className="text-button" onClick={() => chooseDate(localDate())}>Today</button></div></div>
      {view === 'week' ? <><div className="week-grid" role="group" aria-label="Seven-day overview">{weekDates(selected).map(date => { const d = store.days[date] ?? emptyDay(); return <button className={`week-day ${date === selected ? 'selected' : ''}`} key={date} aria-pressed={date === selected} onClick={() => chooseDate(date)}><span>{dateLabel(date, { weekday: 'short' })}</span><strong>{dateLabel(date, { day: 'numeric' })}</strong>{[...d.activities].sort((a,b) => Number(a.status === 'unscheduled')-Number(b.status === 'unscheduled') || minutes(a.start)-minutes(b.start)).slice(0, 3).map(a => <span className={`week-chip ${a.fixed ? 'fixed-chip' : ''}`} key={a.id}><small>{a.status === 'unscheduled' ? 'Unscheduled' : a.status === 'completed' ? `${a.start} · Done` : a.start} · {a.fixed ? 'Fixed' : 'Flexible'}</small>{a.title}</span>)}{!d.activities.length && <span className="helper">Room to plan</span>}{d.activities.length > 3 && <span className="helper">+ {d.activities.length - 3} more</span>}{d.interruptions.length > 0 && <span className="week-alert">{d.interruptions.length} interruption{d.interruptions.length > 1 ? 's' : ''}</span>}</button>; })}</div><section className="week-selected"><div><h2>{dateLabel(selected)}</h2><p className="helper">{day.activities.length} planned activities. Each day is rescued separately.</p></div><button className="button primary" onClick={() => { setView('day'); setEditor({ type: 'activity', date: selected }); }}>Plan an activity</button><button className="button secondary" onClick={() => setView('day')}>Open this day</button></section></> : <>
      {day.demo && <div className="demo-notice"><strong>Sample day · Hand-authored demo activities</strong><p>No AI produced these activities. Edits are stored locally. Generated proposals, if separately requested, are labeled below.</p><button className="text-button" onClick={() => { if (window.confirm('Clear this sample day and its local edits?')) update(selected, changeDay(day, { activities: [], interruptions: [], demo: false })); }}>Clear sample day</button></div>}
      <div className="day-layout"><section className="schedule-area" aria-label="Day plan">
        {day.activities.length === 0 ? <div className="empty-state"><div className="empty-sun" aria-hidden="true"><span/></div><h2>Your day starts here.</h2><p>A little structure, with room for real life.<br/>Add what matters, one activity at a time.</p><button className="button primary" onClick={() => setEditor({ type: 'activity', date: selected })}>Make your day</button><button className="text-button" onClick={sample}>Try a sample day <span className="badge neutral">Demo data</span></button></div> : <><div className="section-heading"><h2>Your planned activities</h2><button className="button secondary" onClick={() => setEditor({ type: 'activity', date: selected })}>+ Add activity</button></div><p className="helper">Time passing does not complete a task. Mark it done when you decide.</p>
        {selected === localDate(now) && <div className="now-marker"><span className="dot" aria-hidden="true"/><strong>Now {localClock(now)}</strong><span>{current ? `Happening now: ${current.title}` : next ? `Up next: ${next.title} at ${next.start}` : 'No upcoming pending activity'}</span></div>}
        <ol className="timeline">{sorted.map(a => <ActivityCard key={a.id} activity={a} dayDate={selected} now={now} edit={() => setEditor({ type: 'activity', date: selected, value: a })} complete={() => update(selected, changeDay(day, { activities: day.activities.map(x => x.id === a.id ? { ...x, status: x.status === 'completed' ? 'pending' : 'completed' } : x) }))}/>)}</ol>
        {postponed.length > 0 && <section className="unscheduled"><h2>Still unscheduled</h2><p>These activities are not assigned a time or moved to another day.</p>{postponed.map(a => <div key={a.id}><strong>{a.title}</strong><button className="text-button" onClick={() => setEditor({ type: 'activity', date: selected, value: a })}>Edit & schedule</button></div>)}</section>}</>}
        <details className="settings" key={selected}><summary>Day settings</summary><p className="helper">These bounds apply only to the selected day. Future days use 00:00 as the pending-work clock.</p><form onSubmit={e => { e.preventDefault(); const fields = new FormData(e.currentTarget); const start = String(fields.get('start')), end = String(fields.get('end')); if (minutes(end) <= minutes(start)) { setServiceError('The day end must be later than its start.'); return; } update(selected, changeDay(day, { start, end })); }}><div className="form-row"><div><label htmlFor="day-start">Day starts</label><input id="day-start" name="start" type="time" defaultValue={day.start} required/></div><div><label htmlFor="day-end">Day ends</label><input id="day-end" name="end" type="time" defaultValue={day.end} required/></div></div><button className="button secondary" type="submit">Save day settings</button></form></details>
        {day.history.length > 0 && <button className="text-button" onClick={() => { try { if (update(selected, undoPlan(day))) setNotice('Previous plan restored. Undo does not claim the original plan is feasible now.'); } catch (e) { setServiceError(errorMessage(e)); } }}>Undo applied plan</button>}
        </section><aside className="day-aside"><div className="rescue-note"><div className="sun-drawing" aria-hidden="true"><span/></div><h2>Life happens.<br/>Let’s make room.</h2><p>A new appointment? A late start? Add what changed, then review a revised day.</p><button className="button interruption-button" onClick={() => setEditor({ type: 'event', date: selected })}>Something changed?</button></div><div className="legend"><h3>A little guide to your plan</h3><p><span className="badge fixed">Fixed</span> Keeps its time and duration.</p><p><span className="badge flexible">Flexible</span> Can move. Shortens only if allowed.</p><p className="helper">Priority expresses what matters. It does not guarantee a particular outcome.</p></div></aside></div>
      <section className="interruptions"><div className="section-heading"><h2>What changed</h2><button className="text-button" onClick={() => setEditor({ type: 'event', date: selected })}>Add interruption</button></div>{!day.interruptions.length && <p className="helper">No interruptions added. Keep going at your pace.</p>}{day.interruptions.map(event => { const items = affected(day, event); return <article className="event-card" key={event.id}><div className="section-heading"><h3>{event.title}</h3><button className="text-button" aria-label={`Edit interruption ${event.title}`} onClick={() => setEditor({ type: 'event', date: selected, value: event })}>Edit</button></div><p>{event.start}–{event.end} · Unavoidable busy time</p><p>{items.length ? `Overlaps: ${items.map(a => `${a.title} (${a.fixed ? 'Fixed' : 'Flexible'})`).join(', ')}` : 'No activity overlaps detected. This is not proof of full feasibility.'}</p>{items.filter(a => a.fixed).map(a => <div className="fixed-conflict" key={a.id}><strong>{a.title} cannot move automatically.</strong><button className="text-button" onClick={() => setEditor({ type: 'activity', date: selected, value: a })}>Review this commitment</button></div>)}</article>; })}</section>
      <section className="rescue-panel"><div><h2>A different shape for your day?</h2><p>Python checks hard constraints. You review the tradeoffs before applying anything.</p><p className="helper" id="live-status">{health === null ? 'The local Python service is unavailable. Planning still works in this browser.' : health.evidence === 'offline_fixture' ? 'Offline integration test: the SDK uses only hand-authored MockTransport completions. No Meta requests.' : health.live_enabled ? 'Live AI is enabled on the local server. Rescue makes one proposal and at most one correction.' : 'Live AI is disabled on the server. You can still check this day with Python.'}</p></div><div className="rescue-actions"><button className="button secondary" disabled={busy || !pending.length} onClick={() => checkOrRescue(false)}>Check day with Python</button><button className="button primary" aria-describedby="live-status" disabled={busy || !health?.live_enabled || !pending.length || selected < localDate(now)} onClick={() => checkOrRescue(true)}>{busy ? 'Checking your day…' : 'Rescue my day'}</button></div></section>
      {serviceError && <div className="feedback error" role="alert">{serviceError}</div>}
      {check && <section className={`feedback ${check.conflicts.length ? 'warning' : 'notice'}`} role="status"><h2>{check.conflicts.length ? 'Some commitments need your attention.' : 'Python checked the fixed commitments.'}</h2><p>{check.message}</p>{check.conflicts.length > 0 && <><p>Fixed activities keep their time and duration. Explicitly edit a commitment or interruption to resolve the conflict.</p><ul>{[...new Set(check.conflicts.flatMap(c => c.activity_ids))].map(id => <li key={id}>{day.activities.find(a => a.id === id)?.title ?? 'Affected activity'}</li>)}</ul><details><summary>Technical conflict details</summary><pre>{JSON.stringify(check.conflicts, null, 2)}</pre></details></>}</section>}
      {activeReview && <section className="proposal" aria-label="Rescue proposal"><h2>Your rescued day</h2>{accepted ? <><div className="outcome"><h3>A revised plan to review.</h3><p>{activeReview.response.validation!.kept_ids.length} kept, {activeReview.response.validation!.moved_or_adjusted_ids.length} moved or adjusted, {activeReview.response.validation!.postponed_ids.length} postponed.</p><p>This is not a claim of an optimal schedule.</p></div><p className="helper">{activeReview.response.evidence === 'offline_fixture' ? 'Offline hand-authored test proposal' : activeReview.response.evidence === 'muse' ? 'Muse-generated proposal' : 'Provider proposal'} · Python checked the request snapshot at {activeReview.checkedAt}. Apply rechecks the current local clock.</p><div className="comparison"><section><h3>Before</h3><ol className="timeline">{pending.map(a => <ActivityCard key={a.id} activity={a} now={now} dayDate={selected}/>)}</ol></section><section><h3>After</h3><ol className="timeline">{[...activeReview.response.plan!.scheduled].sort((a,b) => a.start_minute-b.start_minute).map(item => { const original = pending.find(a => a.id === item.activity_id); if (!original) return null; const changes = [item.start_minute !== minutes(original.start) ? `Moved from ${original.start} to ${clock(item.start_minute)}` : '', item.duration_minutes < original.duration ? `Shortened from ${original.duration} to ${item.duration_minutes} min` : ''].filter(Boolean).join(' · ') || 'Kept at the same time and duration'; return <ActivityCard key={original.id} activity={{ ...original, start: clock(item.start_minute), duration: item.duration_minutes }} now={now} dayDate={selected} change={changes}/>; })}</ol></section></div><div className="unscheduled"><h3>Postponed · Still unscheduled</h3>{activeReview.response.plan!.postponed_ids.length ? activeReview.response.plan!.postponed_ids.map(id => <p key={id}>{pending.find(a => a.id === id)?.title} — not assigned to another day.</p>) : <p>None. All pending activities are included in the proposal.</p>}</div><details><summary>Model rationale · Unverified</summary><p className="rationale">{activeReview.response.rationale || 'No model rationale was provided.'}</p><p className="helper">This explanation is not independently verified.</p></details><div className="proposal-actions"><button className="button primary" onClick={() => setConfirmApply(true)}>Apply this plan</button><button className="button secondary" onClick={() => { setReview(null); setNotice('Original plan kept. Nothing was overwritten.'); }}>Keep original plan</button></div></> : <div className="feedback error" role="alert"><p>{activeReview.response.message}</p><p>No accepted proposal is available. Your original plan is unchanged.</p></div>}<details><summary>Advanced: Python validation & execution trace</summary><pre>{JSON.stringify({ status: activeReview.response.status, validation: activeReview.response.validation, issues: activeReview.response.issues, trace: activeReview.response.trace }, null, 2)}</pre></details></section>}
      </>}
      <footer className="page-footer"><strong translate="no">DayRescue</strong><span>Plans change. You still have a day.</span><span>Browser-local storage · No cloud sync</span></footer>
    </main></div></div>
    {editor?.type === 'activity' && <ActivityForm key={`${editor.date}-${editor.value?.id ?? 'new'}`} date={editor.date} activity={editor.value} close={() => setEditor(null)} save={saveActivity} remove={editor.value ? () => update(editor.date, changeDay(getDay(editor.date), { activities: getDay(editor.date).activities.filter(a => a.id !== editor.value!.id) })) : undefined}/>}
    {editor?.type === 'event' && <InterruptionForm key={`${editor.date}-${editor.value?.id ?? 'new'}`} date={editor.date} event={editor.value} close={() => setEditor(null)} save={saveEvent} remove={editor.value ? () => update(editor.date, changeDay(getDay(editor.date), { interruptions: getDay(editor.date).interruptions.filter(b => b.id !== editor.value!.id) })) : undefined}/>}
    {confirmApply && activeReview && <Modal title="Apply this revised plan?" close={() => { if (!applying) setConfirmApply(false); }}><p>This changes only {dateLabel(selected)} in this browser. Completed tasks stay separate, and postponed tasks remain unscheduled. A snapshot of your prior plan is kept for undo.</p><p className="helper">Python will check the proposal again against the current clock before it is applied.</p><div className="modal-actions"><button className="button secondary" disabled={applying} onClick={() => setConfirmApply(false)}>Cancel</button><button className="button primary" disabled={applying} onClick={accept}>{applying ? 'Rechecking with Python…' : 'Confirm & apply'}</button></div></Modal>}
  </>;
}
