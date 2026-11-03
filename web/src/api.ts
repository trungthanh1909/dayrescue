import type { DayInput, Issue, Plan, Validation } from './state';
export type Preflight = { fingerprint: string; conflicts: Issue[]; message: string; validation?: Validation };
export type Proposal = { fingerprint: string; status: string; message: string; evidence?: string; plan: Plan | null; validation: Validation | null; conflicts: Issue[]; issues: string[]; trace: Record<string, unknown>[]; rationale: string };
export async function apiCall<T>(path: string, body?: unknown): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), path === '/rescue' ? 300000 : 15000);
  try {
    const response = await fetch(`/api${path}`, { method: body === undefined ? 'GET' : 'POST',
      headers: body === undefined ? {} : { 'Content-Type': 'application/json', 'X-DayRescue-Action': path === '/rescue' ? 'rescue' : 'validate' },
      body: body === undefined ? undefined : JSON.stringify(body), signal: controller.signal, cache: 'no-store' });
    const data = await response.json();
    if (!response.ok) throw new Error(typeof data.message === 'string' ? data.message : typeof data.detail === 'string' ? data.detail : 'Check the input times, names, durations and day window. No revised plan was applied.');
    return data as T;
  } catch (error) {
    if (error instanceof Error && error.name !== 'TypeError' && error.name !== 'AbortError' && error.name !== 'SyntaxError') throw error;
    throw new Error('The local service did not respond. Your plan is unchanged. Check the service before making another explicit request.');
  } finally { clearTimeout(timer); }
}
export const preflight = (day: DayInput) => apiCall<Preflight>('/validate', { day });
