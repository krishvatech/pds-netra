import { clearSession, getToken } from '@/lib/auth';
import type {
  Camera,
  CameraCreate,
  CameraUpdate,
  EdgeDevice,
  EdgeDeviceCreate,
  EdgeDeviceUpdate,
  EmailCheckResponse,
  LoginResponse,
  PasswordVerifyResponse,
  RuleType,
  RuleTypeCreate,
  RuleTypeUpdate,
  SessionResponse,
  User
} from '@/lib/types';

export class ApiError extends Error {
  status: number;
  body: any;

  constructor(status: number, body: any) {
    super(body?.detail || `API ${status}`);
    this.status = status;
    this.body = body;
  }
}

async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers || {});
  const token = getToken();
  if (token) headers.set('Authorization', `Bearer ${token}`);
  if (options.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');

  const resp = await fetch(`/api/v1${path}`, {
    ...options,
    headers,
    credentials: 'include'
  });

  if (resp.status === 401) {
    clearSession();
    if (typeof window !== 'undefined') window.location.href = '/auth/login';
  }

  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new ApiError(resp.status, body);
  }

  if (resp.status === 204) return null as T;
  return (await resp.json()) as T;
}

export type SignupInput = {
  first_name: string;
  last_name: string;
  email: string;
  phone?: string;
  password: string;
  confirm_password: string;
};

export type LoginInput = {
  email: string;
  password: string;
};

export type AccountUpdateInput = {
  first_name?: string;
  last_name?: string;
  email?: string;
  phone?: string | null;
  password?: string;
  confirm_password?: string;
};

export type PasswordVerifyInput = {
  password: string;
};

export async function signup(payload: SignupInput): Promise<LoginResponse> {
  return apiFetch<LoginResponse>('/auth/signup', {
    method: 'POST',
    body: JSON.stringify(payload)
  });
}

export async function login(payload: LoginInput): Promise<LoginResponse> {
  return apiFetch<LoginResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify(payload)
  });
}

export async function logout(): Promise<void> {
  await apiFetch('/auth/logout', { method: 'POST' });
  clearSession();
}

export async function getSession(): Promise<SessionResponse> {
  return apiFetch<SessionResponse>('/auth/session');
}

export async function getAccount(): Promise<User> {
  return apiFetch<User>('/auth/account');
}

export async function getUsers(): Promise<User[]> {
  return apiFetch<User[]>('/auth/users');
}

export async function updateAccount(payload: AccountUpdateInput): Promise<User> {
  return apiFetch<User>('/auth/account', {
    method: 'PUT',
    body: JSON.stringify(payload)
  });
}

export async function verifyPassword(payload: PasswordVerifyInput): Promise<PasswordVerifyResponse> {
  return apiFetch<PasswordVerifyResponse>('/auth/verify-password', {
    method: 'POST',
    body: JSON.stringify(payload)
  });
}

export async function checkEmail(email: string): Promise<EmailCheckResponse> {
  const params = new URLSearchParams({ email });
  return apiFetch<EmailCheckResponse>(`/auth/check-email?${params.toString()}`);
}

export async function getCameras(): Promise<Camera[]> {
  return apiFetch<Camera[]>('/cameras');
}

export async function createCamera(payload: CameraCreate): Promise<Camera> {
  return apiFetch<Camera>('/cameras', {
    method: 'POST',
    body: JSON.stringify(payload)
  });
}

export async function updateCamera(id: string, payload: CameraUpdate): Promise<Camera> {
  return apiFetch<Camera>(`/cameras/${id}`, {
    method: 'PUT',
    body: JSON.stringify(payload)
  });
}

export async function deleteCamera(id: string): Promise<void> {
  await apiFetch(`/cameras/${id}`, { method: 'DELETE' });
}

export async function approveCamera(id: string, edgeId: string): Promise<Camera> {
  return apiFetch<Camera>(`/cameras/${id}/approve`, {
    method: 'POST',
    body: JSON.stringify({ edge_id: edgeId })
  });
}

export async function unassignCamera(id: string): Promise<Camera> {
  return apiFetch<Camera>(`/cameras/${id}/unassign`, { method: 'POST' });
}

export async function getEdgeDevices(userId?: string): Promise<EdgeDevice[]> {
  const params = userId ? `?user_id=${encodeURIComponent(userId)}` : '';
  return apiFetch<EdgeDevice[]>(`/edge-devices${params}`);
}

export async function createEdgeDevice(payload: EdgeDeviceCreate): Promise<EdgeDevice> {
  return apiFetch<EdgeDevice>('/edge-devices', {
    method: 'POST',
    body: JSON.stringify(payload)
  });
}

export async function updateEdgeDevice(id: string, payload: EdgeDeviceUpdate): Promise<EdgeDevice> {
  return apiFetch<EdgeDevice>(`/edge-devices/${id}`, {
    method: 'PUT',
    body: JSON.stringify(payload)
  });
}

export async function deleteEdgeDevice(id: string): Promise<void> {
  await apiFetch(`/edge-devices/${id}`, { method: 'DELETE' });
}

export async function getRuleTypes(): Promise<RuleType[]> {
  return apiFetch<RuleType[]>('/rule-types');
}

export async function createRuleType(payload: RuleTypeCreate): Promise<RuleType> {
  return apiFetch<RuleType>('/rule-types', {
    method: 'POST',
    body: JSON.stringify(payload)
  });
}

export async function updateRuleType(id: string, payload: RuleTypeUpdate): Promise<RuleType> {
  return apiFetch<RuleType>(`/rule-types/${id}`, {
    method: 'PUT',
    body: JSON.stringify(payload)
  });
}

export async function deleteRuleType(id: string): Promise<void> {
  await apiFetch(`/rule-types/${id}`, { method: 'DELETE' });
}

export async function getLiveCameras(): Promise<Camera[]> {
  return apiFetch<Camera[]>('/live');
}

export async function uploadFrame(cameraId: string, blob: Blob): Promise<void> {
  const token = getToken();
  const form = new FormData();
  form.append('file', blob, 'frame.jpg');
  const headers = new Headers();
  if (token) headers.set('Authorization', `Bearer ${token}`);

  const resp = await fetch(`/api/v1/live/frame/${cameraId}`, {
    method: 'POST',
    headers,
    body: form,
    credentials: 'include'
  });

  if (!resp.ok && resp.status !== 204) {
    const body = await resp.json().catch(() => ({}));
    throw new ApiError(resp.status, body);
  }
}
