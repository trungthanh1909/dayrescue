import { describe, expect, it } from 'vitest';
import fixture from './fixtures/rescue.json';
import { STORAGE_KEY, applyPlan, changeDay, dayInput, emptyStore, loadStore, localDate, moveDate, parseDate, parseStore, saveStore, signature, undoPlan, weekDates, type Day, type Plan } from '../src/state';

const date = '2026-11-04';
const day = () => parseStore(JSON.stringify({ version: 1, writeId: 'seed', days: { [date]: fixture.day } })).days[date];

describe('browser-local planning records', () => {
  it('starts truly empty and does not fabricate a user plan', () => {
    expect(loadStore(localStorage).store.days).toEqual({});
    expect(localStorage.getItem(STORAGE_KEY)).toBeNull();
  });
  it('round-trips dated plans, interruption records and accepted revisions, without model text', () => {
    const before = day();
    const applied = applyPlan(date, before, fixture.response.plan, signature(date, before), true);
    saveStore(localStorage, { version: 1, writeId: 'one', days: { [date]: applied } });
    const read = loadStore(localStorage);
    expect(read.error).toBe(''); expect(read.store.days[date]).toEqual(applied);
    expect(read.store.days[date].activities.find(a => a.id === 'read')!.status).toBe('unscheduled');
    expect(read.store.days[date].history).toHaveLength(1);
    expect(localStorage.getItem(STORAGE_KEY)).not.toContain('unverified()');
    expect(localStorage.getItem(STORAGE_KEY)).not.toContain('fingerprint');
    expect(undoPlan(read.store.days[date]).activities).toEqual(before.activities);
  });
  it('keeps completed tasks separate from the scheduling payload and from acceptance', () => {
    const before = day(); before.activities.push({ ...before.activities[0], id: 'done', title: 'Already done', status: 'completed' });
    expect(dayInput(date, before, new Date(2026,10,3,8)).activities.map(a => a.id)).toEqual(['study','call','read']);
    const result = applyPlan(date, before, fixture.response.plan, signature(date, before), true);
    expect(result.activities.find(a => a.id === 'done')).toEqual(before.activities[3]);
    expect(dayInput(date, result, new Date(2026,10,3,8)).activities.map(a => a.id)).toEqual(['study','call']);
  });
  it('requires confirmation and the exact dated input snapshot', () => {
    const before = day(), sig = signature(date, before);
    expect(() => applyPlan(date, before, fixture.response.plan, sig, false)).toThrow();
    expect(() => applyPlan('2026-11-05', before, fixture.response.plan, sig, true)).toThrow();
    const changed = changeDay(before, { end: '23:00' });
    expect(() => applyPlan(date, changed, fixture.response.plan, sig, true)).toThrow();
    expect(before.activities[0].start).toBe('09:00');
  });
  it('rejects unknown or missing response IDs rather than corrupting stored activities', () => {
    const before = day(); const bad: Plan = { scheduled: [], postponed_ids: ['unknown'] };
    expect(() => applyPlan(date, before, bad, signature(date, before), true)).toThrow();
  });
  it('protects edits made after acceptance from a destructive undo', () => {
    const before = day(); const applied = applyPlan(date, before, fixture.response.plan, signature(date, before), true);
    expect(() => undoPlan(changeDay(applied, { end: '21:00' }))).toThrow('protect newer edits');
  });
  it('rejects unknown storage versions and preserves their original contents', () => {
    const raw = '{"version":99,"days":{"important":"do not overwrite"}}'; localStorage.setItem(STORAGE_KEY,raw);
    expect(loadStore(localStorage).blocked).toBe(true);
    expect(localStorage.getItem(STORAGE_KEY)).toBe(raw);
  });
  it('rejects malformed dates and duplicate IDs in storage', () => {
    expect(() => parseStore(JSON.stringify({version:1,writeId:'x',days:{'2026-02-30':fixture.day}}))).toThrow();
    const value = day(); value.activities[1].id = value.activities[0].id;
    expect(() => parseStore(JSON.stringify({version:1,writeId:'x',days:{[date]:value}}))).toThrow();
  });
  it('reports unavailable storage instead of claiming persistence', () => {
    const storage = {getItem: () => {throw new Error('disabled');}};
    expect(loadStore(storage).blocked).toBe(true);
    expect(() => saveStore({setItem: () => {throw new Error('quota');}},emptyStore())).toThrow('quota');
  });
  it('uses local dates, supports Monday-based weeks and never schedules a past day', () => {
    const local = new Date(2026,10,3,23,45);
    expect(localDate(local)).toBe('2026-11-03');
    expect(localDate(parseDate(moveDate('2026-12-31',1)))).toBe('2027-01-01');
    expect(weekDates('2026-11-04')).toEqual(['2026-11-02','2026-11-03','2026-11-04','2026-11-05','2026-11-06','2026-11-07','2026-11-08']);
    expect(() => dayInput('2026-11-02',day(),local)).toThrow('today and future');
    expect(dayInput(date,day(),local).now).toBe('00:00');
  });
});
