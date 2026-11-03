// Browser storage and presentation conversion only. Python validates scheduling constraints.
export type Priority = 'high' | 'medium' | 'low';
export type Activity = { id: string; title: string; start: string; duration: number; priority: Priority; fixed: boolean; minimum: number | null; status: 'pending' | 'completed' | 'unscheduled' };
export type Interruption = { id: string; title: string; start: string; end: string };
export type Content = { activities: Activity[]; interruptions: Interruption[]; start: string; end: string; demo: boolean };
export type Revision = { id: string; at: string; appliedRevision: number; before: Content };
export type Day = Content & { revision: number; history: Revision[] };
export type Store = { version: 1; writeId: string; days: Record<string, Day> };
export type Plan = { scheduled: { activity_id: string; start_minute: number; duration_minutes: number }[]; postponed_ids: string[]; explanation?: string };
export type Validation = { valid: boolean; issues: Issue[]; kept_ids: string[]; moved_or_adjusted_ids: string[]; postponed_ids: string[] };
export type Issue = { code: string; message: string; activity_ids: string[] };
export type DayInput = { date: string; revision: number; now: string; day_start: string; day_end: string; activities: { id: string; title: string; start_time: string; duration_minutes: number; priority: Priority; fixed: boolean; min_duration_minutes: number | null }[]; busy_windows: { label: string; start_time: string; end_time: string }[] };
export const STORAGE_KEY = 'dayrescue.plans.v1';
export const emptyStore = (): Store => ({ version: 1, writeId: '', days: {} });
export const emptyDay = (): Day => ({ activities: [], interruptions: [], start: '07:00', end: '22:00', demo: false, revision: 0, history: [] });
export const uid = () => crypto.randomUUID();
export const localDate = (d = new Date()) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
export const parseDate = (key: string) => new Date(`${key}T12:00:00`);
export const validDate = (key: string) => /^\d{4}-\d{2}-\d{2}$/.test(key) && !Number.isNaN(parseDate(key).getTime()) && localDate(parseDate(key)) === key;
export function moveDate(key: string, offset: number) { const d = parseDate(key); d.setDate(d.getDate() + offset); return localDate(d); }
export function weekDates(key: string) { const d = parseDate(key); const monday = moveDate(key, -((d.getDay() + 6) % 7)); return Array.from({ length: 7 }, (_, i) => moveDate(monday, i)); }
export const minutes = (s: string) => Number(s.slice(0, 2)) * 60 + Number(s.slice(3));
export const clock = (n: number) => `${String(Math.floor(n / 60)).padStart(2, '0')}:${String(n % 60).padStart(2, '0')}`;
export const localClock = (d: Date) => clock(d.getHours() * 60 + d.getMinutes());
export const dateLabel = (key: string, options: Intl.DateTimeFormatOptions = { weekday: 'long', day: 'numeric', month: 'long' }) => new Intl.DateTimeFormat(undefined, options).format(parseDate(key));
export const signature = (date: string, day: Day) => JSON.stringify([date, day]);
export const overlaps = (a: number, b: number, c: number, d: number) => a < d && c < b; // Visual preview only.
export function affected(day: Day, event: Interruption) { return day.activities.filter(a => a.status === 'pending' && overlaps(minutes(a.start), minutes(a.start) + a.duration, minutes(event.start), minutes(event.end))); }
export function dayInput(date: string, day: Day, now = new Date()): DayInput {
  if (date < localDate(now)) throw new Error('Rescue works for today and future days. Choose a current day; elapsed tasks are never marked completed automatically.');
  const activities = day.activities.filter(a => a.status === 'pending');
  if (!activities.length) throw new Error('Add or schedule at least one pending activity before checking this day.');
  return { date, revision: day.revision, now: date === localDate(now) ? localClock(now) : '00:00', day_start: day.start, day_end: day.end,
    activities: activities.map(a => ({ id: a.id, title: a.title, start_time: a.start, duration_minutes: a.duration, priority: a.priority, fixed: a.fixed, min_duration_minutes: a.minimum })),
    busy_windows: day.interruptions.map(b => ({ label: b.title, start_time: b.start, end_time: b.end })) };
}
export function content(day: Day): Content { return structuredClone({ activities: day.activities, interruptions: day.interruptions, start: day.start, end: day.end, demo: day.demo }); }
export function changeDay(day: Day, update: Partial<Content>): Day { return { ...day, ...update, revision: day.revision + 1 }; }
export function applyPlan(date: string, day: Day, plan: Plan, originalSignature: string, confirmed: boolean): Day {
  if (!confirmed || originalSignature !== signature(date, day)) throw new Error('This proposal is stale or has not been confirmed.');
  // Coverage guards protect stored records; these do not decide schedule feasibility.
  const pending = day.activities.filter(a => a.status === 'pending').map(a => a.id);
  const ids = [...plan.scheduled.map(i => i.activity_id), ...plan.postponed_ids];
  if (new Set(ids).size !== ids.length || ids.length !== pending.length || ids.some(id => !pending.includes(id))) throw new Error('The proposal does not match the pending activity records.');
  const scheduled = new Map(plan.scheduled.map(i => [i.activity_id, i]));
  const activities = day.activities.map(a => {
    if (a.status !== 'pending') return a;
    if (plan.postponed_ids.includes(a.id)) return { ...a, status: 'unscheduled' as const };
    const item = scheduled.get(a.id)!;
    return { ...a, start: clock(item.start_minute), duration: item.duration_minutes };
  });
  const revision = day.revision + 1;
  return { ...day, activities, revision, history: [...day.history.slice(-4), { id: uid(), at: new Date().toISOString(), appliedRevision: revision, before: content(day) }] };
}
export function undoPlan(day: Day): Day {
  const last = day.history.at(-1);
  if (!last || day.revision !== last.appliedRevision) throw new Error('The plan changed after acceptance. Undo is unavailable to protect newer edits.');
  const history = day.history.slice(0, -1);
  const revision = day.revision + 1;
  if (history.length) history[history.length - 1] = { ...history.at(-1)!, appliedRevision: revision };
  return { ...structuredClone(last.before), revision, history };
}

// Versioned record validation is about storage shape, never scheduling validity.
const object = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v);
const text = (v: unknown, max = 120): v is string => typeof v === 'string' && v.length > 0 && v.length <= max;
const time = (v: unknown): v is string => typeof v === 'string' && /^([01]\d|2[0-3]):[0-5]\d$/.test(v);
const integer = (v: unknown): v is number => typeof v === 'number' && Number.isInteger(v);
function readContent(v: unknown): Content {
  if (!object(v) || !Array.isArray(v.activities) || v.activities.length > 8 || !Array.isArray(v.interruptions) || v.interruptions.length > 10 || !time(v.start) || !time(v.end) || typeof v.demo !== 'boolean') throw new Error('Invalid stored day');
  const activities: Activity[] = v.activities.map((a: unknown) => {
    if (!object(a) || !text(a.id, 64) || !/^[a-zA-Z0-9_-]+$/.test(a.id) || !text(a.title) || !time(a.start) || !integer(a.duration) || a.duration < 1 || a.duration > 1440 || !['high', 'medium', 'low'].includes(String(a.priority)) || typeof a.fixed !== 'boolean' || !(a.minimum === null || integer(a.minimum)) || !['pending', 'completed', 'unscheduled'].includes(String(a.status))) throw new Error('Invalid stored activity');
    return { id: a.id, title: a.title, start: a.start, duration: a.duration, priority: a.priority as Priority, fixed: a.fixed, minimum: a.minimum as number | null, status: a.status as Activity['status'] };
  });
  const interruptions: Interruption[] = v.interruptions.map((b: unknown) => {
    if (!object(b) || !text(b.id, 64) || !text(b.title) || !time(b.start) || !time(b.end)) throw new Error('Invalid stored interruption');
    return { id: b.id, title: b.title, start: b.start, end: b.end };
  });
  if (new Set([...activities.map(a => a.id), ...interruptions.map(b => b.id)]).size !== activities.length + interruptions.length) throw new Error('Duplicate record IDs');
  return { activities, interruptions, start: v.start, end: v.end, demo: v.demo };
}
export function parseStore(raw: string): Store {
  const v: unknown = JSON.parse(raw);
  if (!object(v) || v.version !== 1 || typeof v.writeId !== 'string' || !object(v.days) || Object.keys(v.days).length > 1000) throw new Error('Unknown storage version');
  const days: Record<string, Day> = {};
  for (const [key, value] of Object.entries(v.days)) {
    if (!validDate(key) || !object(value) || !integer(value.revision) || value.revision < 0 || !Array.isArray(value.history) || value.history.length > 5) throw new Error('Invalid stored date');
    const history: Revision[] = value.history.map((r: unknown) => {
      if (!object(r) || !text(r.id, 64) || !text(r.at, 64) || !integer(r.appliedRevision)) throw new Error('Invalid stored revision');
      return { id: r.id, at: r.at, appliedRevision: r.appliedRevision, before: readContent(r.before) };
    });
    days[key] = { ...readContent(value), revision: value.revision, history };
  }
  return { version: 1, writeId: v.writeId, days };
}
export function loadStore(storage: Pick<Storage, 'getItem'>): { store: Store; error: string; blocked: boolean } {
  try { const raw = storage.getItem(STORAGE_KEY); return { store: raw ? parseStore(raw) : emptyStore(), error: '', blocked: false }; }
  catch { return { store: emptyStore(), error: 'Saved plans could not be read. They have not been overwritten. Reset browser storage explicitly to start fresh.', blocked: true }; }
}
export function saveStore(storage: Pick<Storage, 'setItem'>, store: Store) { storage.setItem(STORAGE_KEY, JSON.stringify(parseStore(JSON.stringify(store)))); }
