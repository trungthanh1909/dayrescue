import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, expect, it } from 'vitest';
import { Timeline } from '../src/Timeline';
import type { Activity, Interruption } from '../src/state';

let root: Root | undefined;
afterEach(async()=>{if(root) await act(async()=>root!.unmount());root=undefined;});
const activity: Activity={id:'task',title:'Focus & study <script>',start:'09:00',duration:120,priority:'high',fixed:false,minimum:null,status:'pending'};
async function render(activities:Activity[],interruptions:Interruption[]) {
  const host=document.createElement('div');document.body.append(host);root=createRoot(host);
  await act(async()=>root!.render(<Timeline label="Mixed schedule" activities={activities} interruptions={interruptions} dayDate="2026-11-04" now={new Date(2026,10,4,9,45)}/>));
  return host;
}

it('preserves overlapping intervals and chronological ordering without mutating source records',async()=>{
  const events:Interruption[]=[{id:'late',title:'Delivery',start:'10:00',end:'10:45'},{id:'early',title:'Visitor <script>',start:'09:15',end:'10:15'}];
  const original=JSON.stringify([activity,events]);
  const host=await render([activity],events);
  expect([...host.querySelectorAll('ol>li')].map(li=>li.getAttribute('data-record-id'))).toEqual(['task','early','late']);
  expect(host.querySelector('[data-record-id="early"]')?.textContent).toContain('09:15–10:15');
  expect(host.querySelector('[data-record-id="late"]')?.textContent).toContain('10:00–10:45');
  expect(host.querySelector('[data-record-id="task"]')?.textContent).toContain('09:00–11:00');
  expect(host.textContent).toContain('Busy now'); expect(host.querySelector('script')).toBeNull();
  expect(host.textContent).toContain('Visitor <script>');expect(JSON.stringify([activity,events])).toBe(original);
});

it('deduplicates by busy-record identity while preserving distinct events with identical labels and times',async()=>{
  const event={id:'busy',title:'Visitor',start:'09:00',end:'10:00'};
  const host=await render([activity],[event,{...event},{...event,id:'other'}]);
  expect([...host.querySelectorAll('[data-timeline-kind="busy"]')].map(li=>li.getAttribute('data-record-id'))).toEqual(['busy','other']);
  expect(host.querySelectorAll('[data-timeline-kind="activity"]')).toHaveLength(1);
});

it('keeps unscheduled work out of timed cards and preserves Fixed/Flexible classification',async()=>{
  const host=await render([activity,{...activity,id:'fixed',title:'Fixed call',fixed:true,start:'12:00'}, {...activity,id:'unscheduled',title:'Reading later',status:'unscheduled'}],[]);
  expect(host.querySelectorAll('ol>li')).toHaveLength(2);
  expect(host.querySelector('[data-record-id="fixed"]')?.classList.contains('fixed-card')).toBe(true);
  expect(host.querySelector('[data-record-id="task"]')?.textContent).toContain('Flexible');
  expect(host.textContent).not.toContain('Reading later');
});
