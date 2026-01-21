import type {
  AlertDetail,
  AlertItem,
  EventItem,
  GodownDetail,
  GodownHealth,
  GodownListItem,
  HealthSummary,
  LoginResponse,
  OverviewData,
  Paginated,
  Severity,
  TestRunDetail,
  TestRunItem
} from './types';
import { getToken } from './auth';

const BASE_URL = '';// Prefer Next.js rewrites (/api/...) to avoid CORS in local dev.

type Query = Record<string, string | number | boolean | null | undefined>;

function buildQuery(query?: Query): string {
  if (!query) return '';
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(query)) {
    if (v === null || v === undefined || v === '') continue;
    params.set(k, String(v));
  }
  const s = params.toString();
  return s ? `?${s}` : '';
}

async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const url = `${BASE_URL}${path}`;
  const token = typeof window !== 'undefined' ? getToken() : null;

  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...(init.headers ?? {})
  };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const resp = await fetch(url, {
    ...init,
    headers,
    cache: 'no-store'
  });

  if (!resp.ok) {
    const text = await resp.text().catch(() => '');
    throw new Error(`API ${resp.status}: ${text || resp.statusText}`);
  }

  return (await resp.json()) as T;
}

async function apiFetchForm<T>(path: string, form: FormData): Promise<T> {
  const url = `${BASE_URL}${path}`;
  const token = typeof window !== 'undefined' ? getToken() : null;
  const headers: HeadersInit = token ? { Authorization: `Bearer ${token}` } : {};

  const resp = await fetch(url, {
    method: 'POST',
    body: form,
    headers,
    cache: 'no-store'
  });

  if (!resp.ok) {
    const text = await resp.text().catch(() => '');
    throw new Error(`API ${resp.status}: ${text || resp.statusText}`);
  }

  return (await resp.json()) as T;
}

export async function login(username: string, password: string): Promise<LoginResponse> {
  return apiFetch<LoginResponse>('/api/v1/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password })
  });
}

export async function getGodowns(params?: {
  district?: string;
  has_open_alerts?: boolean;
  page?: number;
  page_size?: number;
}): Promise<Paginated<GodownListItem> | GodownListItem[]> {
  const q = buildQuery(params);
  return apiFetch(`/api/v1/godowns${q}`);
}

export async function getGodownDetail(godownId: string): Promise<GodownDetail> {
  return apiFetch(`/api/v1/godowns/${encodeURIComponent(godownId)}`);
}

export async function getAlerts(params?: {
  godown_id?: string;
  district?: string;
  alert_type?: string;
  severity?: Severity;
  status?: 'OPEN' | 'CLOSED';
  date_from?: string;
  date_to?: string;
  page?: number;
  page_size?: number;
}): Promise<Paginated<AlertItem> | AlertItem[]> {
  const q = buildQuery(params);
  return apiFetch(`/api/v1/alerts${q}`);
}

export async function getAlertDetail(alertId: string): Promise<AlertDetail> {
  return apiFetch(`/api/v1/alerts/${encodeURIComponent(alertId)}`);
}

export async function getEvents(params?: {
  godown_id?: string;
  camera_id?: string;
  event_type?: string;
  severity?: Severity;
  date_from?: string;
  date_to?: string;
  plate_text?: string;
  person_id?: string;
  page?: number;
  page_size?: number;
}): Promise<Paginated<EventItem> | EventItem[]> {
  const q = buildQuery(params);
  return apiFetch(`/api/v1/events${q}`);
}

export async function getHealthSummary(): Promise<HealthSummary> {
  return apiFetch('/api/v1/health/summary');
}

export async function getGodownHealth(godownId: string): Promise<GodownHealth> {
  return apiFetch(`/api/v1/health/godowns/${encodeURIComponent(godownId)}`);
}

export async function getOverviewData(): Promise<OverviewData> {
  return apiFetch('/api/v1/overview');
}

export async function createTestRun(form: FormData): Promise<TestRunItem> {
  return apiFetchForm<TestRunItem>('/api/v1/test-runs', form);
}

export async function getTestRuns(): Promise<TestRunItem[]> {
  return apiFetch('/api/v1/test-runs');
}

export async function getTestRunDetail(runId: string): Promise<TestRunDetail> {
  return apiFetch(`/api/v1/test-runs/${encodeURIComponent(runId)}`);
}

export async function activateTestRun(runId: string): Promise<{ run: TestRunItem; status: string; override_path: string }> {
  return apiFetch(`/api/v1/test-runs/${encodeURIComponent(runId)}/activate`, { method: 'POST' });
}

export async function deactivateTestRun(runId: string): Promise<{ run: TestRunItem; status: string; override_path: string }> {
  return apiFetch(`/api/v1/test-runs/${encodeURIComponent(runId)}/deactivate`, { method: 'POST' });
}
