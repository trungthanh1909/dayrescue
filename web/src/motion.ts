import { useEffect, type RefObject } from 'react';

// Content is visible by default. Observer/animation failure cannot hide it.
export function useProgressiveReveal(root: RefObject<HTMLElement | null>) {
  useEffect(() => {
    const node = root.current;
    const media = window.matchMedia?.('(prefers-reduced-motion: reduce)');
    if (!node || !media || typeof IntersectionObserver === 'undefined') return;
    const seen = new WeakSet<Element>();
    const watched = new WeakSet<Element>();
    const animations = new Set<Animation>();
    let observer: IntersectionObserver | undefined;
    let mutations: MutationObserver | undefined;
    const stop = () => { observer?.disconnect(); mutations?.disconnect(); animations.forEach(a => a.cancel()); animations.clear(); };
    const observe = () => node.querySelectorAll<HTMLElement>('[data-reveal]').forEach(el => {
      if (!watched.has(el) && !seen.has(el)) { watched.add(el); observer?.observe(el); }
    });
    const start = () => {
      if (media.matches) return;
      try {
        observer = new IntersectionObserver(entries => entries.forEach(entry => {
          if (!entry.isIntersecting) return;
          observer?.unobserve(entry.target);
          if (seen.has(entry.target)) return;
          seen.add(entry.target);
          if (media.matches) return;
          try {
            const animation = (entry.target as HTMLElement).animate?.(
              [{ opacity: 0.35, transform: 'translateY(8px)' }, { opacity: 1, transform: 'translateY(0)' }],
              { duration: 280, easing: 'ease-out' });
            if (animation) { animations.add(animation); animation.onfinish = () => animations.delete(animation); }
          } catch { /* Already visible. Motion is optional. */ }
        }), { threshold: 0.08 });
        observe(); mutations = new MutationObserver(observe); mutations.observe(node, { childList: true, subtree: true });
      } catch { stop(); }
    };
    const preference = () => { stop(); }; // Preference changes leave existing content still.
    start(); media.addEventListener('change', preference);
    return () => { stop(); media.removeEventListener('change', preference); };
  }, [root]);
}
