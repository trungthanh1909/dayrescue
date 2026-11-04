import type { DayInput, Issue, Plan, Validation } from './state';
export type Preflight = { fingerprint: string; conflicts: Issue[]; message: string; validation?: Validation };
export type Proposal = { fingerprint: string; status: string; message: string; evidence?: string; plan: Plan | null; validation: Validation | null; conflicts: Issue[]; issues: string[]; trace: Record<string, unknown>[]; rationale: string };
export class ServiceUnavailableError extends Error {
  constructor() { super('Planning service unavailable. Your plan is unchanged. Retry the connection before requesting a new plan.'); }
}
export class AIDisabledError extends Error {
  constructor() { super('AI planning is currently disabled. Your original plan is unchanged. Conflict checking is still available.'); }
}
export async function apiCall<T>(path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  const controller = new AbortController();
  const abort = () => controller.abort();
  if (signal?.aborted) controller.abort(); else signal?.addEventListener('abort', abort, { once: true });
  const timer = setTimeout(abort, path === '/rescue' ? 300000 : path === '/health' ? 5000 : 15000);
  try {
    const response = await fetch(`/api${path}`, { method: body === undefined ? 'GET' : 'POST',
      headers: body === undefined ? {} : { 'Content-Type': 'application/json', 'X-DayRescue-Action': path === '/rescue' ? 'rescue' : 'validate' },
      body: body === undefined ? undefined : JSON.stringify(body), signal: controller.signal, cache: 'no-store' });
    if (response.status >= 502 && response.status <= 504) throw new ServiceUnavailableError();
    const data = await response.json();
    if (path === '/rescue' && response.status === 403 && typeof data.detail === 'string' && data.detail.startsWith('Live AI is disabled')) throw new AIDisabledError();
    if (!response.ok) throw new Error(typeof data.message === 'string' ? data.message : typeof data.detail === 'string' ? data.detail : 'Check the input times, names, durations and day window. No revised plan was applied.');
    return data as T;
  } catch (error) {
    if (error instanceof Error && error.name !== 'TypeError' && error.name !== 'AbortError' && error.name !== 'SyntaxError') throw error;
    throw new ServiceUnavailableError();
  } finally { clearTimeout(timer); signal?.removeEventListener('abort', abort); }
}
export const preflight = (day: DayInput) => apiCall<Preflight>('/validate', { day });
