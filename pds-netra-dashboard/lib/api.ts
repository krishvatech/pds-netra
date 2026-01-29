import type {
  AlertDetail,
  AlertItem,
  EventItem,
  GodownDetail,
  GodownHealth,
  GodownListItem,
  HealthSummary,
  LoginResponse,
  MovementSummary,
  MovementTimelinePoint,
  OverviewData,
  Paginated,
  RuleItem,
  DispatchIssueItem,
  DispatchTraceItem,
  AlertActionItem,
  AlertStatus,
  Severity,
  TestRunDetail,
  TestRunItem,
  AfterHoursPolicy,
  AfterHoursPolicyAudit,
  WatchlistPerson,
  WatchlistMatchEvent,
  VehicleGateSession,
  AlertDelivery,
  NotificationEndpoint,
  AlertReport,
  CameraInfo,
  CameraModules
} from './types';
import { getToken, getUser } from './auth';

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
  const user = typeof window !== 'undefined' ? getUser() : null;

  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...(init.headers ?? {})
  };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  if (user?.role) headers['X-User-Role'] = user.role;
  if (user?.godown_id) headers['X-User-Godown'] = String(user.godown_id);
  if (user?.district) headers['X-User-District'] = String(user.district);
  if (user?.name) headers['X-User-Name'] = String(user.name);

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
  const user = typeof window !== 'undefined' ? getUser() : null;
  const headers: HeadersInit = token ? { Authorization: `Bearer ${token}` } : {};
  if (user?.role) headers['X-User-Role'] = user.role;
  if (user?.godown_id) headers['X-User-Godown'] = String(user.godown_id);
  if (user?.district) headers['X-User-District'] = String(user.district);
  if (user?.name) headers['X-User-Name'] = String(user.name);

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

export async function getCameras(params?: {
  godown_id?: string;
  role?: string;
  is_active?: boolean;
}): Promise<CameraInfo[]> {
  const q = buildQuery(params);
  return apiFetch(`/api/v1/cameras${q}`);
}

export async function getCameraZones(cameraId: string): Promise<{ camera_id: string; godown_id: string; zones: Array<{ id: string; polygon: number[][] }> }> {
  return apiFetch(`/api/v1/cameras/${encodeURIComponent(cameraId)}/zones`);
}

export async function updateCameraZones(
  cameraId: string,
  zones: Array<{ id: string; polygon: number[][] }>
): Promise<{ camera_id: string; godown_id: string; zones: Array<{ id: string; polygon: number[][] }> }> {
  return apiFetch(`/api/v1/cameras/${encodeURIComponent(cameraId)}/zones`, {
    method: 'PUT',
    body: JSON.stringify({ zones })
  });
}

export async function createCamera(payload: {
  camera_id: string;
  godown_id: string;
  label?: string;
  role?: string;
  rtsp_url: string;
  is_active?: boolean;
  modules?: CameraModules;
}): Promise<CameraInfo> {
  return apiFetch('/api/v1/cameras', {
    method: 'POST',
    body: JSON.stringify(payload)
  });
}

export async function updateCamera(
  cameraId: string,
  payload: { label?: string; role?: string; rtsp_url?: string; is_active?: boolean; modules?: CameraModules }
): Promise<CameraInfo> {
  return apiFetch(`/api/v1/cameras/${encodeURIComponent(cameraId)}`, {
    method: 'PUT',
    body: JSON.stringify(payload)
  });
}

export async function deleteCamera(cameraId: string): Promise<{ status: string; camera_id: string }> {
  return apiFetch(`/api/v1/cameras/${encodeURIComponent(cameraId)}`, { method: 'DELETE' });
}

export async function acknowledgeAlert(alertId: string | number): Promise<{ status: string; alert_id: number }> {
  return apiFetch(`/api/v1/alerts/${encodeURIComponent(String(alertId))}/ack`, { method: 'POST' });
}


export async function getLiveCameras(godownId: string): Promise<{ godown_id: string; cameras: string[] }> {
  return apiFetch(`/api/v1/live/${encodeURIComponent(godownId)}`);
}

export async function getAlerts(params?: {
  godown_id?: string;
  district?: string;
  alert_type?: string;
  severity?: Severity;
  status?: AlertStatus;
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

export async function getAlertActions(alertId: string): Promise<{ items: AlertActionItem[]; total: number }> {
  return apiFetch(`/api/v1/alerts/${encodeURIComponent(alertId)}/actions`);
}

export async function getAlertDeliveries(alertId: string): Promise<AlertDelivery[]> {
  return apiFetch(`/api/v1/alerts/${encodeURIComponent(alertId)}/deliveries`);
}

export async function getNotificationEndpoints(params?: {
  scope?: string;
  godown_id?: string;
  channel?: string;
}): Promise<NotificationEndpoint[]> {
  const q = buildQuery(params);
  return apiFetch(`/api/v1/notification/endpoints${q}`);
}

export async function createNotificationEndpoint(payload: {
  scope: 'HQ' | 'GODOWN' | string;
  godown_id?: string | null;
  channel: 'WHATSAPP' | 'EMAIL' | string;
  target: string;
  is_enabled?: boolean;
}): Promise<NotificationEndpoint> {
  return apiFetch('/api/v1/notification/endpoints', {
    method: 'POST',
    body: JSON.stringify(payload)
  });
}

export async function updateNotificationEndpoint(
  endpointId: string,
  payload: { scope?: string; godown_id?: string | null; channel?: string; target?: string; is_enabled?: boolean }
): Promise<NotificationEndpoint> {
  return apiFetch(`/api/v1/notification/endpoints/${encodeURIComponent(endpointId)}`, {
    method: 'PATCH',
    body: JSON.stringify(payload)
  });
}

export async function deleteNotificationEndpoint(endpointId: string): Promise<{ status: string; id: string }> {
  return apiFetch(`/api/v1/notification/endpoints/${encodeURIComponent(endpointId)}`, {
    method: 'DELETE'
  });
}

export async function getHqReports(limit = 30): Promise<AlertReport[]> {
  return apiFetch(`/api/v1/reports/hq?limit=${encodeURIComponent(String(limit))}`);
}

export async function generateHqReport(period: '24h' | '1h' = '24h'): Promise<AlertReport> {
  return apiFetch(`/api/v1/reports/hq/generate?period=${encodeURIComponent(period)}`, { method: 'POST' });
}

export async function getHqReportDeliveries(reportId: string): Promise<AlertDelivery[]> {
  return apiFetch(`/api/v1/reports/hq/${encodeURIComponent(reportId)}/deliveries`);
}

export async function getVehicleGateSessions(params?: {
  status?: string;
  godown_id?: string;
  q?: string;
  date_from?: string;
  date_to?: string;
  page?: number;
  page_size?: number;
}): Promise<Paginated<VehicleGateSession>> {
  const q = buildQuery(params);
  return apiFetch(`/api/v1/vehicle-gate-sessions${q}`);
}

export async function createAlertAction(alertId: string, payload: { action_type: string; actor?: string; note?: string }): Promise<AlertActionItem> {
  return apiFetch(`/api/v1/alerts/${encodeURIComponent(alertId)}/actions`, {
    method: 'POST',
    body: JSON.stringify(payload)
  });
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

export async function getMovementSummary(params?: {
  godown_id?: string;
  camera_id?: string;
  zone_id?: string;
  date_from?: string;
  date_to?: string;
}): Promise<MovementSummary> {
  const q = buildQuery(params);
  return apiFetch(`/api/v1/reports/movement/summary${q}`);
}

export async function getMovementTimeline(params?: {
  bucket?: 'hour' | 'day';
  godown_id?: string;
  camera_id?: string;
  zone_id?: string;
  date_from?: string;
  date_to?: string;
}): Promise<{ bucket: string; items: MovementTimelinePoint[]; range?: { from?: string | null; to?: string | null } }> {
  const q = buildQuery(params);
  return apiFetch(`/api/v1/reports/movement/timeline${q}`);
}

export function exportAlertsCsvUrl(params?: {
  godown_id?: string;
  status?: string;
  date_from?: string;
  date_to?: string;
}): string {
  const q = buildQuery(params);
  return `/api/v1/reports/alerts/export${q}`;
}

export function exportMovementCsvUrl(params?: {
  godown_id?: string;
  camera_id?: string;
  zone_id?: string;
  date_from?: string;
  date_to?: string;
}): string {
  const q = buildQuery(params);
  return `/api/v1/reports/movement/export${q}`;
}

export async function getDispatchTrace(params?: {
  godown_id?: string;
  status?: string;
  date_from?: string;
  date_to?: string;
}): Promise<{ items: DispatchTraceItem[]; total: number }> {
  const q = buildQuery(params);
  return apiFetch(`/api/v1/reports/dispatch-trace${q}`);
}

export async function getDispatchIssues(params?: {
  godown_id?: string;
  status?: string;
}): Promise<{ items: DispatchIssueItem[]; total: number }> {
  const q = buildQuery(params);
  return apiFetch(`/api/v1/dispatch-issues${q}`);
}

export async function createDispatchIssue(payload: {
  godown_id: string;
  camera_id?: string | null;
  zone_id?: string | null;
  issue_time_utc: string;
}): Promise<DispatchIssueItem> {
  return apiFetch('/api/v1/dispatch-issues', {
    method: 'POST',
    body: JSON.stringify(payload)
  });
}

export async function getRules(params?: {
  godown_id?: string;
  camera_id?: string;
  zone_id?: string;
  type?: string;
  enabled?: boolean;
}): Promise<{ items: RuleItem[]; total: number }> {
  const q = buildQuery(params);
  return apiFetch(`/api/v1/rules${q}`);
}

export async function getAfterHoursPolicy(godownId: string): Promise<AfterHoursPolicy> {
  return apiFetch(`/api/v1/after-hours/policies/${encodeURIComponent(godownId)}`);
}

export async function getAfterHoursPolicies(params?: { godown_id?: string }): Promise<{ items: AfterHoursPolicy[]; total: number }> {
  const q = buildQuery(params);
  return apiFetch(`/api/v1/after-hours/policies${q}`);
}

export async function getAfterHoursPolicyAudit(
  godownId: string,
  params?: { limit?: number }
): Promise<{ items: AfterHoursPolicyAudit[]; total: number }> {
  const q = buildQuery(params);
  return apiFetch(`/api/v1/after-hours/policies/${encodeURIComponent(godownId)}/audit${q}`);
}

export async function updateAfterHoursPolicy(
  godownId: string,
  payload: Partial<AfterHoursPolicy>
): Promise<AfterHoursPolicy> {
  return apiFetch(`/api/v1/after-hours/policies/${encodeURIComponent(godownId)}`, {
    method: 'PUT',
    body: JSON.stringify(payload)
  });
}

export async function createRule(payload: Partial<RuleItem> & {
  godown_id: string;
  camera_id: string;
  zone_id: string;
  type: string;
}): Promise<RuleItem> {
  return apiFetch('/api/v1/rules', {
    method: 'POST',
    body: JSON.stringify(payload)
  });
}

export async function updateRule(ruleId: number, payload: Partial<RuleItem>): Promise<RuleItem> {
  return apiFetch(`/api/v1/rules/${ruleId}`, {
    method: 'PUT',
    body: JSON.stringify(payload)
  });
}

export async function deleteRule(ruleId: number): Promise<{ status: string; id: number }> {
  return apiFetch(`/api/v1/rules/${ruleId}`, { method: 'DELETE' });
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

export async function deleteTestRun(runId: string): Promise<{ status: string; run_id: string }> {
  return apiFetch(`/api/v1/test-runs/${encodeURIComponent(runId)}`, { method: 'DELETE' });
}

export async function getTestRunSnapshots(
  runId: string,
  cameraId: string,
  params?: { page?: number; page_size?: number }
): Promise<{ items: string[]; page: number; page_size: number; total: number }> {
  const q = params ? buildQuery(params as Record<string, any>) : '';
  return apiFetch(`/api/v1/test-runs/${encodeURIComponent(runId)}/snapshots/${encodeURIComponent(cameraId)}${q}`);
}

export async function getWatchlistPersons(params?: {
  status?: string;
  q?: string;
  page?: number;
  page_size?: number;
}): Promise<Paginated<WatchlistPerson>> {
  const q = buildQuery(params);
  return apiFetch(`/api/v1/watchlist/persons${q}`);
}

export async function createWatchlistPerson(form: FormData): Promise<WatchlistPerson> {
  return apiFetchForm('/api/v1/watchlist/persons', form);
}

export async function updateWatchlistPerson(personId: string, payload: Partial<WatchlistPerson>): Promise<WatchlistPerson> {
  return apiFetch(`/api/v1/watchlist/persons/${encodeURIComponent(personId)}`, {
    method: 'PATCH',
    body: JSON.stringify(payload)
  });
}

export async function deactivateWatchlistPerson(personId: string): Promise<WatchlistPerson> {
  return apiFetch(`/api/v1/watchlist/persons/${encodeURIComponent(personId)}/deactivate`, {
    method: 'POST'
  });
}

export async function getWatchlistPerson(personId: string): Promise<WatchlistPerson> {
  return apiFetch(`/api/v1/watchlist/persons/${encodeURIComponent(personId)}`);
}

export async function addWatchlistImages(personId: string, form: FormData): Promise<WatchlistPerson> {
  return apiFetchForm(`/api/v1/watchlist/persons/${encodeURIComponent(personId)}/images`, form);
}

export async function getWatchlistMatches(
  personId: string,
  params?: { page?: number; page_size?: number; date_from?: string; date_to?: string }
): Promise<Paginated<WatchlistMatchEvent>> {
  const q = buildQuery(params);
  return apiFetch(`/api/v1/watchlist/persons/${encodeURIComponent(personId)}/matches${q}`);
}
