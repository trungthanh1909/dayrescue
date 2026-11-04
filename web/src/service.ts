import { useCallback, useEffect, useRef, useState } from 'react';
import { apiCall } from './api';

type Health = { live_enabled: boolean; evidence?: string };
export function usePlanningService() {
  const [health, setHealth] = useState<Health | null>(null);
  const [checking, setChecking] = useState(true);
  const mounted = useRef(false);
  const request = useRef<AbortController | null>(null);
  const retry = useCallback(async () => {
    if (!mounted.current || request.current) return;
    const controller = new AbortController(); request.current = controller; setChecking(true);
    try {
      const value = await apiCall<Health>('/health', undefined, controller.signal);
      if (!value || typeof value.live_enabled !== 'boolean') throw new Error('Unexpected health response');
      if (!controller.signal.aborted && mounted.current) setHealth(value);
    } catch {
      if (!controller.signal.aborted && mounted.current) setHealth(null);
    } finally {
      if (request.current === controller) request.current = null;
      if (!controller.signal.aborted && mounted.current) setChecking(false);
    }
  }, []);
  useEffect(() => {
    mounted.current = true; void retry();
    // Poll health only. Reconnection never resumes an interrupted check or generation.
    const timer = window.setInterval(() => { if (document.visibilityState !== 'hidden') void retry(); }, 15000);
    const focus = () => { void retry(); };
    window.addEventListener('focus', focus);
    return () => { mounted.current = false; window.clearInterval(timer); window.removeEventListener('focus', focus); request.current?.abort(); request.current = null; };
  }, [retry]);
  const markUnavailable = () => setHealth(null);
  return { health, checking, retry, markUnavailable };
}
