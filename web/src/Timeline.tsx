import { clock, dateLabel, localClock, localDate, minutes, type Activity, type Interruption } from './state';

function ActivityCard({ activity: a, dayDate, now, edit, complete, change, headingLevel = 3 }: { activity: Activity; dayDate: string; now: Date; edit?: () => void; complete?: () => void; change?: string; headingLevel?: 3 | 4 }) {
  const Heading = headingLevel === 4 ? 'h4' : 'h3';
  const today = dayDate === localDate(now); const minute = minutes(localClock(now));
  const current = today && a.status === 'pending' && minutes(a.start) <= minute && minute < minutes(a.start) + a.duration;
  const elapsed = today && a.status === 'pending' && minutes(a.start) + a.duration <= minute;
  return <li data-timeline-kind="activity" data-record-id={a.id} className={`activity ${a.fixed ? 'fixed-card' : ''} ${a.status === 'completed' ? 'completed' : ''} ${change?.startsWith('Moved') || change?.includes('Shortened') ? 'adjusted-card' : ''}`}>
    <div className="activity-heading"><div><Heading>{a.title}</Heading><div className="activity-meta"><span>{a.start}–{clock(minutes(a.start) + a.duration)}</span><span>{a.duration} min</span><span>{a.priority} priority</span></div></div><span className={`badge ${a.fixed ? 'fixed' : 'flexible'}`}>{a.fixed ? 'Fixed' : 'Flexible'}</span></div>
    <p className="permission">{a.minimum !== null && !a.fixed ? `May shorten to ${a.minimum} min` : 'Shortening not allowed'}</p>
    {change && <p className="change">{change}</p>}
    {current && <span className="badge current">Happening now</span>}{elapsed && <span className="helper">Elapsed · Still pending</span>}
    {a.status === 'completed' && <span className="badge fixed">Completed by you</span>}
    {(edit || complete) && <div className="activity-actions">{complete && <label className="completion"><input type="checkbox" checked={a.status === 'completed'} onChange={complete} aria-label={`Mark ${a.title} ${a.status === 'completed' ? 'pending' : 'completed'}`} /> Done</label>}{edit && <button className="text-button" onClick={edit} aria-label={`Edit ${a.title}`}>Edit</button>}</div>}
  </li>;
}

export function activityChange(original: Activity | undefined, updated: Activity): string {
  if (!original) return '';
  return [updated.start !== original.start ? `Moved from ${original.start} to ${updated.start}` : '',
    updated.duration < original.duration ? `Shortened from ${original.duration} to ${updated.duration} min` : ''].filter(Boolean).join(' · ');
}

type TimelineItem = { kind: 'activity'; activity: Activity; key: string; start: number; end: number }
  | { kind: 'busy'; event: Interruption; key: string; start: number; end: number };

export function Timeline({ label, activities, interruptions, dayDate, now, changes = {}, edit, complete, headingLevel = 3 }: {
  label: string; activities: readonly Activity[]; interruptions: readonly Interruption[]; dayDate: string; now: Date;
  changes?: Record<string, string>; edit?: (activity: Activity) => void; complete?: (activity: Activity) => void; headingLevel?: 3 | 4;
}) {
  // Display only: busy records remain separate constraints, never proposal items.
  // Identity, rather than label/time, prevents duplication without merging distinct events.
  const busy = new Map<string, Interruption>();
  interruptions.forEach(event => { if (!busy.has(event.id)) busy.set(event.id, event); });
  const items: TimelineItem[] = [
    ...activities.filter(a => a.status !== 'unscheduled').map(a => ({ kind: 'activity' as const, activity: a, key: `activity:${a.id}`, start: minutes(a.start), end: minutes(a.start)+a.duration })),
    ...[...busy.values()].map(event => ({ kind: 'busy' as const, event, key: `busy:${event.id}`, start: minutes(event.start), end: minutes(event.end) })),
  ];
  items.sort((a,b) => a.start-b.start || Number(a.kind === 'activity')-Number(b.kind === 'activity') || a.end-b.end || a.key.localeCompare(b.key));
  if (!items.length) return null;
  const Heading = headingLevel === 4 ? 'h4' : 'h3';
  const minute = minutes(localClock(now));
  return <ol className="timeline" aria-label={label} data-date={dayDate}>
    {items.map(item => item.kind === 'activity'
      ? <ActivityCard key={item.key} activity={item.activity} dayDate={dayDate} now={now} change={changes[item.activity.id]} headingLevel={headingLevel} edit={edit ? () => edit(item.activity) : undefined} complete={complete ? () => complete(item.activity) : undefined}/>
      : <li key={item.key} className="activity busy-card" data-timeline-kind="busy" data-record-id={item.event.id} data-date={dayDate}>
        <div className="activity-heading"><div><Heading>{item.event.title}</Heading><div className="activity-meta"><time dateTime={`${dayDate}T${item.event.start}`}>{item.event.start}–{item.event.end}</time><span>{item.end-item.start} min</span><span>{dateLabel(dayDate, { day: 'numeric', month: 'short', year: 'numeric' })}</span></div></div><span className="badge busy">Unavoidable busy time</span></div>
        <p className="permission">Reserved by you · stays unchanged in a revised plan.</p>
        {dayDate === localDate(now) && item.start <= minute && minute < item.end && <span className="badge busy">Busy now</span>}
      </li>)}
  </ol>;
}
