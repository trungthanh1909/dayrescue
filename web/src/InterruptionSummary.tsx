import { affected, clock, localClock, localDate, minutes, type Activity, type Day } from './state';

export function InterruptionSummary({ day, date, now, canGenerate, busy, reason, findPlan, edit }: { day: Day; date: string; now: Date; canGenerate: boolean; busy: boolean; reason: string; findPlan: () => void; edit: (activity: Activity) => void }) {
  if (!day.interruptions.length) return null;
  const items = [...new Map(day.interruptions.flatMap(event => affected(day, event)).map(a => [a.id, a])).values()].sort((a,b) => minutes(a.start)-minutes(b.start));
  const fixed = items.filter(a => a.fixed), flexible = items.filter(a => !a.fixed);
  const minute = minutes(localClock(now));
  const active = items.some(a => date === localDate(now) && minutes(a.start) <= minute && minute < minutes(a.start)+a.duration);
  return <section className={`interruption-summary ${fixed.length ? 'needs-attention' : ''}`} aria-label="Affected activities">
    <h2 id="affected-activities-heading" tabIndex={-1}>{fixed.length ? 'A fixed commitment needs your attention.' : 'Make room for what changed.'}</h2>
    <p role="status">{items.length ? `${flexible.length} flexible ${flexible.length === 1 ? 'activity overlaps' : 'activities overlap'} your interruptions${fixed.length ? `, with ${fixed.length} fixed ${fixed.length === 1 ? 'conflict' : 'conflicts'}` : ''}.` : 'No pending activity overlaps the interruptions. This does not guarantee that the whole day will fit.'}</p>
    {!!items.length && <ul>{items.map(a => <li key={a.id}><div><strong>{a.title}</strong><span>{a.start}–{clock(minutes(a.start)+a.duration)} · {a.fixed ? 'Fixed · cannot move automatically' : 'Flexible · can be considered for a new time'}</span>{date === localDate(now) && minutes(a.start) <= minute && minute < minutes(a.start)+a.duration && <span className="active-overlap">In progress · still pending</span>}</div>{a.fixed && <button className="button secondary" onClick={() => edit(a)} aria-label={`Review commitment ${a.title}`}>Review commitment</button>}</li>)}</ul>}
    {active && <p className="helper">Time already spent is not deducted. The full pending activity is included when finding a new plan.</p>}
    {fixed.length ? <p>Fixed commitments keep their time and duration. Review the commitment or edit an interruption before requesting a new plan.</p> : <><div className="next-step"><button className="button primary" disabled={!canGenerate} onClick={findPlan}>{busy ? 'Finding a new plan…' : 'Find a new plan'}</button><p>{reason}</p></div><p className="helper">{reason.startsWith('Offline test') ? 'This test uses hand-authored proposals and never contacts Meta.' : 'After you click, only this day’s pending activities and interruptions are sent to Meta. Review the proposal before applying it.'}</p></>}
  </section>;
}
