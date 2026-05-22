import type { PlanRequest, PlanResponse, Skill, FocusedPlan } from '../types';

const BASE = '';

class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

async function request<T>(
  url: string,
  init?: RequestInit,
  signal?: AbortSignal,
): Promise<T> {
  const res = await fetch(`${BASE}${url}`, { ...init, signal });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch { /* ignore */ }
    throw new ApiError(res.status, detail);
  }
  return res.json();
}

export async function fetchProfessions(signal?: AbortSignal): Promise<string[]> {
  const data = await request<{ professions: string[] }>('/api/professions', undefined, signal);
  return data.professions;
}

export async function fetchSkillsForRole(
  profession: string,
  signal?: AbortSignal,
): Promise<string[]> {
  const data = await request<{ skills: string[] }>(
    `/api/skills-for-role?profession=${encodeURIComponent(profession)}`,
    undefined,
    signal,
  );
  return data.skills;
}

export async function suggestSkills(q: string, signal?: AbortSignal): Promise<string[]> {
  if (q.trim().length < 2) return [];
  const data = await request<{ suggestions: string[] }>(
    `/api/suggest-skills?q=${encodeURIComponent(q.trim())}`,
    undefined,
    signal,
  );
  return data.suggestions;
}

export async function analyzeResume(
  file: File,
  signal?: AbortSignal,
): Promise<{ skills: Skill[]; error?: string }> {
  const form = new FormData();
  form.append('file', file);
  return request<{ skills: Skill[]; error?: string }>(
    '/api/analyze-resume',
    { method: 'POST', body: form },
    signal,
  );
}

export async function buildPlan(
  req: PlanRequest,
  signal?: AbortSignal,
): Promise<PlanResponse> {
  return request<PlanResponse>(
    '/api/plan',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    },
    signal,
  );
}

export async function buildFocusedPlan(
  params: { profession: string; grade: string; scenario: string; target_profession?: string; selected_skills: string[] },
  signal?: AbortSignal,
): Promise<FocusedPlan> {
  return request<FocusedPlan>(
    '/api/focused-plan',
    { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(params) },
    signal,
  );
}

export async function healthCheck(): Promise<boolean> {
  try {
    const data = await request<{ status: string }>('/health');
    return data.status === 'ok';
  } catch {
    return false;
  }
}

export { ApiError };
