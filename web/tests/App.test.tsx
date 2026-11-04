import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import App from '../src/App';
import fixture from './fixtures/rescue.json';
import { STORAGE_KEY, parseStore, saveStore, type Store } from '../src/state';

const date = '2026-11-04';
let root: Root | undefined;
let container: HTMLDivElement;
const seeded = () => parseStore(JSON.stringify({version:1,writeId:'seed',days:{[date]:fixture.day}}));
beforeEach(() => { vi.useFakeTimers(); vi.setSystemTime(new Date(2026,10,3,8)); });
afterEach(async () => { if (root) await act(async () => root!.unmount()); root = undefined; vi.useRealTimers(); });
function reply(value: unknown, status = 200) { return new Response(JSON.stringify(value),{status,headers:{'Content-Type':'application/json'}}); }
function network(live = true, custom?: (path: string, body: any) => Promise<Response> | undefined) {
  const mock = vi.fn(async (url: string | URL | Request, options?: RequestInit) => {
    const path = String(url); const body = options?.body ? JSON.parse(String(options.body)) : undefined;
    const override = custom?.(path,body); if (override) return override;
    if (path === '/api/health') return reply({status:'ok',live_enabled:live});
    if (path === '/api/validate') return reply(body.proposal ? {fingerprint:fixture.response.fingerprint,validation:fixture.response.validation,message:'Python revalidated'} : {fingerprint:fixture.response.fingerprint,conflicts:[],message:'No fixed conflicts. Not proof of full feasibility.'});
    if (path === '/api/rescue') return reply(fixture.response);
    throw new Error(`Unexpected test request: ${path}`);
  });
  vi.stubGlobal('fetch',mock); return mock;
}
async function mount(store?: Store) {
  if (store) { saveStore(localStorage,store); history.replaceState(null,'',`/?date=${date}#day`); }
  container = document.createElement('div'); document.body.append(container); root = createRoot(container);
  await act(async () => { root!.render(<App/>); });
}
function button(name: string) { const node = [...container.querySelectorAll('button')].find(b => b.textContent?.trim() === name || b.getAttribute('aria-label') === name); if (!node) throw new Error(`Missing button: ${name}`); return node; }
async function click(name: string) { await act(async () => button(name).click()); }
async function fill(id: string, value: string) {
  await act(async () => { const group = container.querySelector<HTMLElement>(`fieldset#${id}`);
    if (group) { const [hour,minute] = value.split(':'); for (const [part,next] of [['hour',hour],['minute',minute]]) { const select = group.querySelector<HTMLSelectElement>(`#${id}-${part}`)!; select.value=next; select.dispatchEvent(new Event('change',{bubbles:true})); } return; }
    const node = container.querySelector<HTMLInputElement>(`#${id}`)!;
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value')!.set!.call(node,value);
    node.dispatchEvent(new Event('input',{bubbles:true})); node.dispatchEvent(new Event('change',{bubbles:true})); });
}
const text = () => container.textContent ?? '';
const persisted = () => parseStore(localStorage.getItem(STORAGE_KEY)!);
const rescueCalls = (mock: ReturnType<typeof network>) => mock.mock.calls.filter(c => String(c[0]) === '/api/rescue');

it('first launch is empty; mount and rerender only read health, never generate or seed storage', async () => {
  const mock = network(); await mount();
  expect(text()).toContain('Your day starts here.'); expect(button('Make your day')).toBeTruthy();
  expect(localStorage.getItem(STORAGE_KEY)).toBeNull();
  await act(async () => root!.render(<App/>));
  expect(mock.mock.calls.map(c=>String(c[0]))).toEqual(['/api/health']);
});

it('adds, edits, moves dates and removes an actual activity using accessible forms', async () => {
  network(false); await mount(); await click('Make your day');
  expect(container.querySelector('dialog[aria-labelledby]')).toBeTruthy();
  await fill('activity-name','Practice guitar'); await fill('activity-date',date); await click('Save activity');
  const id = persisted().days[date].activities[0].id;
  expect(text()).toContain('Practice guitar'); await click('Edit Practice guitar');
  await fill('activity-name','Practice piano'); await fill('activity-date','2026-11-05'); await click('Save activity');
  expect(persisted().days[date].activities).toHaveLength(0);
  expect(persisted().days['2026-11-05'].activities[0].id).toBe(id);
  await click('Edit Practice piano'); vi.spyOn(window,'confirm').mockReturnValue(true); await click('Remove activity');
  expect(persisted().days['2026-11-05'].activities).toHaveLength(0);
});

it('never marks elapsed work complete automatically', async () => {
  network(); const store = seeded(); store.days['2026-11-03'] = store.days[date]; delete store.days[date];
  await mount(store); await click('Today');
  await act(async () => { vi.setSystemTime(new Date(2026,10,3,18)); vi.advanceTimersByTime(15000); });
  expect(text()).toContain('Elapsed · Still pending');
  expect(persisted().days['2026-11-03'].activities.every(a=>a.status==='pending')).toBe(true);
});

it('saves the date and time actually displayed by native fields even before a React change event', async () => {
  network(false); await mount(seeded()); await click('Edit Study Python');
  await act(async () => {
    // Models native date/time entry or autofill without a synthetic change event.
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value')!.set!.call(container.querySelector('#activity-date'),'2026-11-05');
    container.querySelector<HTMLSelectElement>('#activity-time-hour')!.value='14';
    container.querySelector<HTMLSelectElement>('#activity-time-minute')!.value='15';
  });
  await fill('activity-name','Native date and time stay intact');
  await click('Save activity');
  expect(persisted().days['2026-11-05'].activities[0].start).toBe('14:15');
  expect(persisted().days[date].activities.some(a=>a.id==='study')).toBe(false);
});

it('respects the frontend live gate and still supports explicit Python checks', async () => {
  const mock = network(false); await mount(seeded());
  expect(button('Rescue my day').disabled).toBe(true);
  await click('Check schedule conflicts'); expect(text()).toContain('Your fixed commitments were checked.');
  expect(rescueCalls(mock)).toHaveLength(0);
});

it('shows fixed conflicts from Python and never calls rescue afterward', async () => {
  const mock=network(true,(path)=>path==='/api/validate'?Promise.resolve(reply({fingerprint:'a'.repeat(64),message:'Fixed conflicts detected.',conflicts:[{code:'FIXED_BUSY_CONFLICT',message:'Conflict',activity_ids:['call']}]})):undefined);
  await mount(seeded()); await click('Rescue my day');
  expect(text()).toContain('Some commitments need your attention.'); expect(text()).toContain('Team check-in');
  expect(rescueCalls(mock)).toHaveLength(0); expect(container.querySelector('[aria-label="Rescue proposal"]')).toBeNull();
});

it('reviews the genuine Python fixture without applying it, then confirms, revalidates and supports persisted undo', async () => {
  const mock=network(); await mount(seeded()); await click('Rescue my day');
  expect(text()).toContain('Moved from 09:00 to 10:30'); expect(text()).toContain('Shortened from 60 to 30 min');
  expect(text()).toContain('Read a chapter — not assigned to another day.');
  expect(persisted().days[date].activities[0].start).toBe('09:00');
  expect(container.querySelector('script')).toBeNull(); expect(text()).toContain('<script>unverified()</script>');
  await click('Apply this plan'); expect(container.querySelector('dialog')).toBeTruthy();
  expect(persisted().days[date].history).toHaveLength(0); await click('Cancel');
  await click('Apply this plan'); await click('Confirm & apply');
  expect(mock.mock.calls.filter(c=>String(c[0])==='/api/validate')).toHaveLength(2);
  expect(persisted().days[date].activities.find(a=>a.id==='study')!.start).toBe('10:30');
  expect(persisted().days[date].activities.find(a=>a.id==='read')!.status).toBe('unscheduled');
  expect(localStorage.getItem(STORAGE_KEY)).not.toContain('unverified()');
  expect(rescueCalls(mock)).toHaveLength(1);
  await click('Undo applied plan'); expect(persisted().days[date].activities[0].start).toBe('09:00');
});

it('can keep the original with no automatic overwrite', async () => {
  network(); await mount(seeded()); const original=localStorage.getItem(STORAGE_KEY);
  await click('Rescue my day'); await click('Keep original plan');
  expect(localStorage.getItem(STORAGE_KEY)).toBe(original); expect(text()).not.toContain('Apply this plan');
});

it('rejects acceptance when Python rejects the current clock, with no extra model call', async () => {
  const mock=network(true,(path,body)=>path==='/api/validate'&&body.proposal?Promise.resolve(reply({fingerprint:fixture.response.fingerprint,validation:{...fixture.response.validation,valid:false}})):undefined);
  await mount(seeded()); await click('Rescue my day'); await click('Apply this plan'); await click('Confirm & apply');
  expect(text()).toContain('The revised plan failed a fresh schedule check'); expect(persisted().days[date].history).toHaveLength(0);
  expect(rescueCalls(mock)).toHaveLength(1);
});

it('discards proposals on underlying edits and on date navigation, without background regeneration', async () => {
  const mock=network(); await mount(seeded()); await click('Rescue my day');
  await click('Edit Study Python'); await fill('activity-name','New priority task'); await click('Save activity');
  expect(text()).not.toContain('Apply this plan'); expect(rescueCalls(mock)).toHaveLength(1);
  await click('Rescue my day'); await click('Next day'); await click('Previous day');
  expect(text()).not.toContain('Apply this plan'); expect(rescueCalls(mock)).toHaveLength(2);
});

it('rejects a response that finishes after an edit', async () => {
  let resolve!: (response: Response)=>void;
  const mock=network(true,(path)=>path==='/api/rescue'?new Promise<Response>(r=>{resolve=r;}):undefined);
  await mount(seeded()); await click('Rescue my day');
  await click('Edit Study Python'); await fill('activity-name','Changed in flight'); await click('Save activity');
  await act(async()=>{resolve(reply(fixture.response));});
  expect(text()).not.toContain('Apply this plan'); expect(text()).toContain('proposal was discarded');
  expect(rescueCalls(mock)).toHaveLength(1);
});

it('clears a proposal after another tab changes the stored plan', async () => {
  network(); await mount(seeded()); await click('Rescue my day');
  await click('Edit Study Python');
  const changed=seeded(); changed.writeId='other-tab'; changed.days[date].revision++;
  await act(async()=>{const raw=JSON.stringify(changed);localStorage.setItem(STORAGE_KEY,raw);window.dispatchEvent(new StorageEvent('storage',{key:STORAGE_KEY,newValue:raw}));});
  expect(text()).not.toContain('Apply this plan'); expect(text()).toContain('another tab');
  expect(container.querySelector('dialog')).toBeNull();
});

it('requires a real boolean live gate, not a truthy value from an unexpected service', async () => {
  network(true,path=>path==='/api/health'?Promise.resolve(reply({live_enabled:'1'})):undefined);
  await mount(seeded()); expect(button('Rescue my day').disabled).toBe(true);
});

it('an explicit sample never populates first launch or replaces an existing future plan', async () => {
  network(false); await mount(); expect(localStorage.getItem(STORAGE_KEY)).toBeNull();
  await click('Try a sample day Demo data');
  expect(text()).toContain('Sample day · Hand-authored demo activities');
  expect(persisted().days[date].activities).toHaveLength(3);
  await click('Today'); await click('Try a sample day Demo data');
  expect(text()).toContain('Your existing plan was not replaced');
  expect(persisted().days[date].activities).toHaveLength(3);
});

it('creates, moves and removes interruption records while keeping busy time unavoidable', async () => {
  network(false); await mount(seeded()); await click('Add interruption');
  await fill('event-name','New appointment'); await fill('event-start','10:15'); await fill('event-end','10:45');
  await act(async()=>container.querySelector<HTMLInputElement>('input[name="unavoidable"]')!.click());
  await click('Save interruption'); expect(text()).toContain('must be unavoidable');
  expect(persisted().days[date].interruptions).toHaveLength(1);
  await act(async()=>container.querySelector<HTMLInputElement>('input[name="unavoidable"]')!.click());
  await click('Save interruption');
  expect(text()).toContain('Team check-in cannot move automatically');
  const id=persisted().days[date].interruptions[1].id;
  await click('Edit interruption New appointment'); await fill('event-date','2026-11-05'); await click('Save interruption');
  expect(persisted().days[date].interruptions).toHaveLength(1);
  expect(persisted().days['2026-11-05'].interruptions[0].id).toBe(id);
  await click('Edit interruption New appointment'); vi.spyOn(window,'confirm').mockReturnValue(true); await click('Remove');
  expect(persisted().days['2026-11-05'].interruptions).toHaveLength(0);
});

it('shows the current activity and only changes completion after an explicit user action', async () => {
  vi.setSystemTime(new Date(2026,10,3,9,15)); network(false);
  const store=seeded(); store.days['2026-11-03']=store.days[date];
  await mount(store); await click('Today');
  expect(text()).toContain('Happening now: Study Python');
  await act(async()=>container.querySelector<HTMLInputElement>('input[aria-label="Mark Study Python completed"]')!.click());
  expect(persisted().days['2026-11-03'].activities[0].status).toBe('completed');
  expect(text()).toContain('Up next: Team check-in');
  await act(async()=>container.querySelector<HTMLInputElement>('input[aria-label="Mark Study Python pending"]')!.click());
  expect(persisted().days['2026-11-03'].activities[0].status).toBe('pending');
});

it('keeps persisted plans across a real React remount and shows seven local dates', async () => {
  network(false); await mount(seeded()); await act(async()=>root!.unmount()); root=undefined;
  await mount(); expect(text()).toContain('Study Python');
  await act(async()=>{const link=[...container.querySelectorAll('nav a')].find(a=>a.textContent?.includes('My week'))! as HTMLAnchorElement; link.click();});
  expect(container.querySelectorAll('.week-day')).toHaveLength(7); expect(text()).toContain('Study Python');
});

it('leaves failed and malformed proposals unapplied and does not display their rationale', async () => {
  const mock=network(true,(path)=>path==='/api/rescue'?Promise.resolve(reply({...fixture.response,status:'provider_error',plan:null,validation:null,rationale:'must not display',message:'The provider failed safely.'})):undefined);
  await mount(seeded()); await click('Rescue my day');
  expect(text()).toContain('No accepted proposal is available'); expect(text()).not.toContain('must not display');
  expect(container.querySelector('[aria-label="Rescue proposal"]')?.hasAttribute('data-reveal')).toBe(false);
  expect(text()).not.toContain('Apply this plan'); expect(rescueCalls(mock)).toHaveLength(1);
});

it('distinguishes an unavailable service and recovers with a health-only retry', async () => {
  let online=false;
  const mock=network(true,path=>path==='/api/health' ? online ? Promise.resolve(reply({live_enabled:true})) : Promise.reject(new TypeError('offline')) : undefined);
  await mount(seeded());
  expect(text()).toContain('Planning service unavailable');
  expect(button('Check schedule conflicts').disabled).toBe(true);
  expect(button('Find a new plan').disabled).toBe(true);
  await click('Retry connection'); expect(text()).toContain('Planning service unavailable');
  online=true; await click('Retry connection');
  expect(text()).toContain('Ready to find a new plan'); expect(button('Find a new plan').disabled).toBe(false);
  expect(mock.mock.calls.every(c=>String(c[0])==='/api/health')).toBe(true);
});

it('polls only health after a late server startup and never resumes a previous action', async () => {
  let online=false;
  const mock=network(false,path=>path==='/api/health' ? online ? Promise.resolve(reply({live_enabled:false})) : Promise.resolve(new Response('',{status:500})) : undefined);
  await mount(seeded()); expect(text()).toContain('Planning service unavailable');
  online=true; await act(async()=>{await vi.advanceTimersByTimeAsync(15000);});
  expect(text()).toContain('AI planning is currently disabled');
  expect(button('Check schedule conflicts').disabled).toBe(false); expect(button('Find a new plan').disabled).toBe(true);
  expect(mock.mock.calls.map(c=>String(c[0]))).toEqual(['/api/health','/api/health']);
});

it('does not overlap health requests and aborts a pending health check on unmount', async () => {
  let signal: AbortSignal | undefined;
  const mock=vi.fn((_url:string, options:RequestInit)=>{signal=options.signal as AbortSignal; return new Promise<Response>(()=>{});});
  vi.stubGlobal('fetch',mock); await mount();
  await act(async()=>{await vi.advanceTimersByTimeAsync(1000);window.dispatchEvent(new Event('focus'));});
  expect(mock).toHaveBeenCalledTimes(1);
  await act(async()=>root!.unmount()); root=undefined;
  expect(signal?.aborted).toBe(true);
});

it('updates availability after a check loses the service and retry never repeats the POST', async () => {
  let fail=true;
  const mock=network(true,path=>path==='/api/validate' && fail ? Promise.reject(new TypeError('connection refused')) : undefined);
  await mount(seeded()); await click('Check schedule conflicts');
  expect(text()).toContain('Planning service unavailable'); expect(button('Rescue my day').disabled).toBe(true);
  fail=false; await click('Retry connection');
  expect(button('Rescue my day').disabled).toBe(false);
  expect(text()).toContain('Connection restored; your original plan is unchanged.');
  expect(mock.mock.calls.filter(c=>String(c[0])==='/api/validate')).toHaveLength(1);
  expect(rescueCalls(mock)).toHaveLength(0);
});

it('times out health safely and retries health without any generation', async () => {
  let online=false;
  const mock=vi.fn((_url:string, options:RequestInit)=>online ? Promise.resolve(reply({live_enabled:false})) : new Promise<Response>((_resolve,reject)=>{options.signal?.addEventListener('abort',()=>reject(new DOMException('Aborted','AbortError')));}));
  vi.stubGlobal('fetch',mock); await mount(seeded());
  await act(async()=>{await vi.advanceTimersByTimeAsync(5000);});
  expect(text()).toContain('Planning service unavailable');
  online=true; await click('Retry connection');
  expect(text()).toContain('AI planning is currently disabled');
  expect(mock.mock.calls.every(c=>c[0]==='/api/health')).toBe(true);
});

it('refreshes health if the server gate changes after an enabled page loaded, without retrying generation', async () => {
  let enabled=true;
  const mock=network(true,path=>path==='/api/health' ? Promise.resolve(reply({live_enabled:enabled})) : path==='/api/rescue' ? (enabled=false, Promise.resolve(reply({detail:'Live AI is disabled in the server process.'},403))) : undefined);
  await mount(seeded()); await click('Find a new plan');
  expect(text()).toContain('AI planning is currently disabled'); expect(button('Rescue my day').disabled).toBe(true);
  expect(rescueCalls(mock)).toHaveLength(1); expect(persisted().days[date].history).toHaveLength(0);
});

it('saves an active Flexible interruption, highlights it, then generates only on its CTA click', async () => {
  vi.setSystemTime(new Date(2026,10,4,9,15));
  const mock=network(); const store=seeded(); store.days[date].interruptions=[];
  await mount(store); await click('Add interruption');
  await fill('event-name','Doorbell'); await fill('event-start','09:15'); await fill('event-end','09:45'); await click('Save interruption');
  const summary=container.querySelector('[aria-label="Affected activities"]')!;
  expect(summary.textContent).toContain('Study Python'); expect(summary.textContent).toContain('In progress · still pending');
  expect(summary.textContent).toContain('Time already spent is not deducted');
  expect(document.activeElement?.id).toBe('affected-activities-heading');
  expect(mock.mock.calls.map(c=>String(c[0]))).toEqual(['/api/health']);
  expect(persisted().days[date].activities.every(a=>a.status==='pending')).toBe(true);
  await click('Find a new plan'); expect(rescueCalls(mock)).toHaveLength(1);
  const body=JSON.parse(String(mock.mock.calls.find(c=>String(c[0])==='/api/rescue')![1]?.body));
  expect(body.day.now).toBe('09:15');
  expect(body.day.activities.find((a:any)=>a.id==='study').duration_minutes).toBe(60);
  expect(text()).toContain('Apply this plan'); expect(persisted().days[date].history).toHaveLength(0);
});

it('offers Review commitment for Fixed overlaps and lets Python preflight block rescue', async () => {
  const mock=network(true,path=>path==='/api/validate'?Promise.resolve(reply({fingerprint:'a'.repeat(64),message:'Fixed conflicts detected.',conflicts:[{code:'FIXED_BUSY_CONFLICT',activity_ids:['call']}]})):undefined);
  await mount(seeded()); await click('Add interruption');
  await fill('event-name','Fixed overlap'); await fill('event-start','10:15'); await fill('event-end','10:45'); await click('Save interruption');
  const summary=container.querySelector('[aria-label="Affected activities"]')!;
  expect(summary.textContent).toContain('fixed conflict');
  expect(summary.querySelector('button')?.textContent).toBe('Review commitment');
  expect([...summary.querySelectorAll('button')].some(b=>b.textContent==='Find a new plan')).toBe(false);
  await click('Review commitment Team check-in'); expect(container.querySelector('dialog')?.textContent).toContain('Edit activity'); await click('Cancel');
  await click('Rescue my day'); expect(rescueCalls(mock)).toHaveLength(0);
  expect(persisted().days[date].activities.find(a=>a.id==='call')!.start).toBe('10:00');
});

it('saving an interruption invalidates an existing proposal without background regeneration', async () => {
  const mock=network(); await mount(seeded()); await click('Find a new plan');
  expect(text()).toContain('Apply this plan'); await click('Add interruption');
  await fill('event-name','Changed inputs'); await click('Save interruption');
  expect(text()).not.toContain('Apply this plan'); expect(rescueCalls(mock)).toHaveLength(1);
  await click('Retry connection'); expect(text()).not.toContain('Apply this plan'); expect(rescueCalls(mock)).toHaveLength(1);
});

it('authors English dates and offers every 24-hour minute with no native time widgets', async () => {
  vi.spyOn(navigator,'language','get').mockReturnValue('vi-VN');
  network(false); await mount(seeded()); expect(text()).toContain('Wednesday 4 November');
  await click('Edit Study Python');
  const hours=container.querySelector<HTMLSelectElement>('#activity-time-hour')!, mins=container.querySelector<HTMLSelectElement>('#activity-time-minute')!;
  expect(hours.getAttribute('aria-label')).toBe('Starts at hour');
  expect([...hours.options].map(o=>o.value)).toEqual(Array.from({length:24},(_,i)=>String(i).padStart(2,'0')));
  expect([...mins.options].map(o=>o.value)).toEqual(Array.from({length:60},(_,i)=>String(i).padStart(2,'0')));
  expect(container.querySelector('input[type="time"]')).toBeNull();
  await fill('activity-time','00:01'); await fill('activity-duration','1'); await fill('activity-minimum','1'); await click('Save activity');
  expect(persisted().days[date].activities.find(a=>a.id==='study')!.start).toBe('00:01');
  await click('Add interruption'); await fill('event-name','Last minute'); await fill('event-start','23:58'); await fill('event-end','23:59'); await click('Save interruption');
  expect(persisted().days[date].interruptions.at(-1)!.end).toBe('23:59');
});

const schedule = (label: string) => container.querySelector<HTMLOListElement>(`ol[aria-label="${label}"]`)!;
const scheduleRecords = (label: string) => [...schedule(label).children].map(li=>`${li.getAttribute('data-timeline-kind')}:${li.getAttribute('data-record-id')}`);

it('shows busy time exactly once in each chronological Before/After timeline without adding it to the proposal', async () => {
  const mock=network(); const store=seeded(); const original=structuredClone(store.days[date].interruptions);
  await mount(store);
  expect(scheduleRecords('Daily schedule')).toEqual(['busy:event','activity:study','activity:call','activity:read']);
  await click('Find a new plan');
  expect(scheduleRecords('Before schedule')).toEqual(['busy:event','activity:study','activity:call','activity:read']);
  expect(scheduleRecords('After schedule')).toEqual(['busy:event','activity:call','activity:study']);
  for (const label of ['Daily schedule','Before schedule','After schedule']) {
    const busy=schedule(label).querySelectorAll('[data-timeline-kind="busy"]');
    expect(busy).toHaveLength(1); expect(busy[0].textContent).toContain('Unexpected visitor');
    expect(busy[0].textContent).toContain('09:00–10:00'); expect(busy[0].getAttribute('data-date')).toBe(date);
    expect(busy[0].querySelector('time')?.dateTime).toBe(`${date}T09:00`);
    expect(busy[0].querySelector('input')).toBeNull();
  }
  expect(schedule('After schedule').querySelector('[data-record-id="study"]')?.classList.contains('adjusted-card')).toBe(true);
  expect(container.querySelector('.unscheduled')?.textContent).toContain('Read a chapter');
  const rescueBody=JSON.parse(String(rescueCalls(mock)[0][1]?.body));
  expect(rescueBody.day.activities.map((a:any)=>a.id)).toEqual(['study','call','read']);
  expect(rescueBody.day.busy_windows).toEqual(fixture.input.busy_windows);
  await click('Apply this plan'); await click('Confirm & apply');
  const acceptedBody=JSON.parse(String(mock.mock.calls.filter(c=>String(c[0])==='/api/validate')[1][1]?.body));
  expect(acceptedBody.proposal.scheduled.map((a:any)=>a.activity_id)).toEqual(['call','study']);
  expect(acceptedBody.proposal.postponed_ids).toEqual(['read']);
  expect(persisted().days[date].interruptions).toEqual(original);
});

it('retains the identical busy record and accepted changes through Apply, reload and Undo', async () => {
  const mock=network(); await mount(seeded()); const original=structuredClone(persisted().days[date].interruptions);
  await click('Find a new plan'); await click('Apply this plan'); await click('Confirm & apply');
  expect(scheduleRecords('Daily schedule')).toEqual(['busy:event','activity:call','activity:study']);
  expect(schedule('Daily schedule').textContent).toContain('Moved from 09:00 to 10:30');
  expect(schedule('Daily schedule').textContent).toContain('Shortened from 60 to 30 min');
  expect(schedule('Daily schedule').textContent).not.toContain('Read a chapter');
  expect(container.querySelector('.unscheduled')?.textContent).toContain('Read a chapter');
  await act(async()=>root!.unmount()); root=undefined; await mount();
  expect(scheduleRecords('Daily schedule')).toEqual(['busy:event','activity:call','activity:study']);
  expect(schedule('Daily schedule').textContent).toContain('Moved from 09:00 to 10:30');
  expect(persisted().days[date].interruptions).toEqual(original);
  await click('Undo applied plan');
  expect(scheduleRecords('Daily schedule')).toEqual(['busy:event','activity:study','activity:call','activity:read']);
  expect(schedule('Daily schedule').textContent).not.toContain('Moved from');
  expect(persisted().days[date].interruptions).toEqual(original);
  await click('Next day'); expect(container.querySelector('ol[aria-label="Daily schedule"]')).toBeNull();
  await click('Previous day'); expect(scheduleRecords('Daily schedule')).toContain('busy:event');
  expect(rescueCalls(mock)).toHaveLength(1);
});

it('renders a busy-only day without inventing an activity or duplicating the editable event', async () => {
  const mock=network(false);const store=seeded();store.days[date].activities=[];
  await mount(store);
  expect(scheduleRecords('Daily schedule')).toEqual(['busy:event']);
  expect(schedule('Daily schedule').textContent).toContain('Unavoidable busy time');
  expect(schedule('Daily schedule').textContent).not.toContain('priority');
  expect(container.querySelector('.interruptions')?.textContent).toContain('Unexpected visitor');
  expect(button('Edit interruption Unexpected visitor')).toBeTruthy();
  expect(rescueCalls(mock)).toHaveLength(0);
});
