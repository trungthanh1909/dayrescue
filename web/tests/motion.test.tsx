import { act, useRef } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, expect, it, vi } from 'vitest';
import { useProgressiveReveal } from '../src/motion';

let root: Root | undefined;
const original = HTMLElement.prototype.animate;
afterEach(async()=>{if(root) await act(async()=>root!.unmount()); root=undefined; HTMLElement.prototype.animate=original;});
function Page({ extra=false }: {extra?: boolean}) { const ref=useRef<HTMLElement>(null);useProgressiveReveal(ref);return <main ref={ref}><section data-reveal>Visible content</section>{extra && <section data-reveal>Later content</section>}<p role="alert">Critical error stays still</p></main>; }
async function mount(extra=false) { const host=document.createElement('div');document.body.append(host);root=createRoot(host);await act(async()=>root!.render(<Page extra={extra}/>)); return host; }

it('keeps content visible and skips observers for reduced motion',async()=>{
  vi.stubGlobal('matchMedia',vi.fn(()=>({matches:true,addEventListener:vi.fn(),removeEventListener:vi.fn()})));
  const observer=vi.fn();vi.stubGlobal('IntersectionObserver',observer); const animate=vi.fn();HTMLElement.prototype.animate=animate;
  const host=await mount();expect(host.textContent).toContain('Visible content');expect(host.querySelector('[data-reveal]')?.getAttribute('style')).toBeNull();expect(observer).not.toHaveBeenCalled();expect(animate).not.toHaveBeenCalled();
});

it('reveals each section once, ignores edits/errors, observes new sections, cancels on reduced motion',async()=>{
  let preference!: ()=>void, callback!: IntersectionObserverCallback;
  const media={matches:false,addEventListener:vi.fn((_event,fn)=>{preference=fn;}),removeEventListener:vi.fn()};
  vi.stubGlobal('matchMedia',vi.fn(()=>media)); const observed:Element[]=[];const disconnect=vi.fn(),unobserve=vi.fn();
  vi.stubGlobal('IntersectionObserver',class { constructor(cb:IntersectionObserverCallback){callback=cb;} observe(el:Element){observed.push(el);} unobserve=unobserve;disconnect=disconnect; });
  const cancel=vi.fn();const animate=vi.fn<HTMLElement['animate']>(()=>({cancel,onfinish:null}) as unknown as Animation);HTMLElement.prototype.animate=animate;
  const host=await mount(); const first=host.querySelector('[data-reveal]')!;
  expect(observed).toEqual([first]);
  callback([{target:first,isIntersecting:true}] as IntersectionObserverEntry[],{} as IntersectionObserver);
  callback([{target:first,isIntersecting:true}] as IntersectionObserverEntry[],{} as IntersectionObserver);
  expect(animate).toHaveBeenCalledTimes(1);expect(animate.mock.calls[0][1]).toMatchObject({duration:280});
  await act(async()=>root!.render(<Page extra/>));expect(observed).toHaveLength(2);
  expect(animate).toHaveBeenCalledTimes(1);expect(host.querySelector('[role="alert"]')?.getAttribute('data-reveal')).toBeNull();
  media.matches=true;preference();expect(cancel).toHaveBeenCalledTimes(1);expect(disconnect).toHaveBeenCalled();
});

it('leaves content visible when observers are unavailable or throw',async()=>{
  vi.stubGlobal('matchMedia',vi.fn(()=>({matches:false,addEventListener:vi.fn(),removeEventListener:vi.fn()})));
  vi.stubGlobal('IntersectionObserver',class { constructor(){throw new Error('unsupported');} });
  const host=await mount();expect(host.textContent).toContain('Visible content');expect(host.querySelector('[data-reveal]')?.getAttribute('style')).toBeNull();
});
