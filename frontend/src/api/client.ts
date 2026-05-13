import type {
  PlanRequest,
  PlanResponse,
  Skill,
  FocusedPlan,
  AuthResponse,
  UserProfile,
  AnalysisRecord,
  ProgressRecord,
  ProgressStatus,
  OnboardingRequest,
  OnboardingResponse,
} from '../types';

const BASE = '';

export const AUTH_ACCESS_STORAGE_KEY = 'career_copilot_jwt';
export const AUTH_REFRESH_STORAGE_KEY = 'career_copilot_refresh';

export class ApiError extends Error {
  status: number;
  code?: string;
  constructor(status: number, message: string, code?: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
  }
}

function parseFastApiDetail(body: unknown): { message: string; code?: string } {
  if (!body || typeof body !== 'object') return { message: 'Ошибка запроса' };
  const raw = (body as { detail?: unknown }).detail;
  if (typeof raw === 'string') return { message: raw };
  if (raw && typeof raw === 'object' && !Array.isArray(raw)) {
    const o = raw as { message?: unknown; code?: unknown };
    if (typeof o.message === 'string') {
      return {
        message: o.message,
        code: typeof o.code === 'string' ? o.code : undefined,
      };
    }
  }
  if (Array.isArray(raw)) {
    const parts = raw.map((item) => {
      if (item && typeof item === 'object' && 'msg' in item) {
        return String((item as { msg?: unknown }).msg ?? '');
      }
      return String(item);
    });
    return { message: parts.filter(Boolean).join('; ') || 'Ошибка запроса' };
  }
  return { message: 'Ошибка запроса' };
}

let refreshInFlight: Promise<void> | null = null;

export function storeAuthTokens(accessToken: string, refreshToken: string): void {
  localStorage.setItem(AUTH_ACCESS_STORAGE_KEY, accessToken);
  localStorage.setItem(AUTH_REFRESH_STORAGE_KEY, refreshToken);
}

export function clearStoredAuthTokens(): void {
  localStorage.removeItem(AUTH_ACCESS_STORAGE_KEY);
  localStorage.removeItem(AUTH_REFRESH_STORAGE_KEY);
}

/** Revokes refresh token on server (best-effort); does not clear local storage. */
export async function revokeRefreshOnServer(): Promise<void> {
  const refreshToken = localStorage.getItem(AUTH_REFRESH_STORAGE_KEY)?.trim();
  if (!refreshToken) return;
  try {
    await fetch(`${BASE}/api/auth/logout`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
  } catch {
    /* ignore network errors */
  }
}

function shouldAttemptTokenRefresh(url: string): boolean {
  if (url.includes('/api/auth/refresh')) return false;
  if (url.includes('/api/auth/login') || url.includes('/api/auth/register')) return false;
  return Boolean(localStorage.getItem(AUTH_REFRESH_STORAGE_KEY)?.trim());
}

async function refreshAccessToken(): Promise<void> {
  const refreshToken = localStorage.getItem(AUTH_REFRESH_STORAGE_KEY)?.trim();
  if (!refreshToken) throw new Error('missing refresh token');

  if (refreshInFlight) {
    await refreshInFlight;
    return;
  }

  refreshInFlight = (async () => {
    const res = await fetch(`${BASE}/api/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      const { message } = parseFastApiDetail(body);
      throw new ApiError(res.status, message);
    }
    const data = (await res.json()) as {
      access_token: string;
      refresh_token: string;
    };
    if (!data.access_token || !data.refresh_token) {
      throw new Error('invalid refresh response');
    }
    storeAuthTokens(data.access_token, data.refresh_token);
  })();

  try {
    await refreshInFlight;
  } finally {
    refreshInFlight = null;
  }
}

async function request<T>(
  url: string,
  init?: RequestInit,
  signal?: AbortSignal,
  didRefresh = false,
): Promise<T> {
  const authToken = localStorage.getItem(AUTH_ACCESS_STORAGE_KEY) || '';
  const initHeaders = new Headers(init?.headers || {});
  if (authToken && !initHeaders.has('Authorization')) {
    initHeaders.set('Authorization', `Bearer ${authToken}`);
  }

  const res = await fetch(`${BASE}${url}`, { ...init, headers: initHeaders, signal });
  if (!res.ok) {
    let body: unknown = {};
    try {
      body = await res.json();
    } catch { /* ignore */ }
    const { message, code } = parseFastApiDetail(body);

    if (
      res.status === 401
      && !didRefresh
      && shouldAttemptTokenRefresh(url)
    ) {
      try {
        await refreshAccessToken();
        return request<T>(url, init, signal, true);
      } catch (err) {
        if (code === 'USER_NOT_FOUND') {
          throw new ApiError(res.status, message, code);
        }
        if (err instanceof ApiError) throw err;
        throw new ApiError(res.status, message, code);
      }
    }

    throw new ApiError(res.status, message, code);
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

export async function fetchSkillsByCategoryForRole(
  profession: string,
  signal?: AbortSignal,
): Promise<Array<{ name: string; skills: string[] }>> {
  const data = await request<{ categories: Array<{ name: string; skills: string[] }> }>(
    `/api/skills-by-category?profession=${encodeURIComponent(profession)}`,
    undefined,
    signal,
  );
  return data.categories;
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

export async function register(
  params: { email: string; password: string },
  signal?: AbortSignal,
): Promise<AuthResponse> {
  return request<AuthResponse>(
    '/api/auth/register',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    },
    signal,
  );
}

export async function login(
  params: { email: string; password: string },
  signal?: AbortSignal,
): Promise<AuthResponse> {
  return request<AuthResponse>(
    '/api/auth/login',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    },
    signal,
  );
}

export async function authMe(signal?: AbortSignal): Promise<{ user: UserProfile }> {
  return request<{ user: UserProfile }>('/api/auth/me', undefined, signal);
}

export async function fetchMe(signal?: AbortSignal): Promise<UserProfile> {
  const data = await request<{ user: UserProfile }>('/api/auth/me', undefined, signal);
  return data.user;
}

export async function saveOnboarding(
  payload: OnboardingRequest,
  signal?: AbortSignal,
): Promise<OnboardingResponse> {
  return request<OnboardingResponse>(
    '/api/auth/onboarding',
    {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    },
    signal,
  );
}

export async function fetchAnalyses(signal?: AbortSignal): Promise<AnalysisRecord[]> {
  const data = await request<{ items: AnalysisRecord[] }>('/api/analyses', undefined, signal);
  return data.items;
}

export async function createAnalysis(
  payload: {
    scenario: string;
    current_role?: string;
    target_role?: string;
    skills_json?: Record<string, unknown>;
    result_json?: Record<string, unknown>;
  },
  signal?: AbortSignal,
): Promise<AnalysisRecord> {
  const data = await request<{ item: AnalysisRecord }>(
    '/api/analyses',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    },
    signal,
  );
  return data.item;
}

export async function fetchAnalysisById(analysisId: string, signal?: AbortSignal): Promise<AnalysisRecord> {
  const data = await request<{ item: AnalysisRecord }>(`/api/analyses/${encodeURIComponent(analysisId)}`, undefined, signal);
  return data.item;
}

export async function fetchSharedAnalysis(
  analysisId: string,
  signal?: AbortSignal,
): Promise<import('../types').SharedAnalysisResponse> {
  return request<import('../types').SharedAnalysisResponse>(
    `/api/share/${encodeURIComponent(analysisId)}`,
    undefined,
    signal,
  );
}

export async function patchProgress(
  payload: { skill_name: string; status: ProgressStatus },
  signal?: AbortSignal,
): Promise<ProgressRecord> {
  const data = await request<{ item: ProgressRecord }>(
    '/api/progress',
    {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    },
    signal,
  );
  return data.item;
}

export async function fetchProgress(signal?: AbortSignal): Promise<ProgressRecord[]> {
  const data = await request<{ items: ProgressRecord[] }>('/api/progress', undefined, signal);
  return data.items;
}

export async function healthCheck(): Promise<boolean> {
  try {
    const data = await request<{ status: string }>('/health');
    return data.status === 'ok';
  } catch {
    return false;
  }
}
