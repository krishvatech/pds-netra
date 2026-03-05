import { clearSession, getToken } from '@/lib/auth';
import type {
  Camera,
  CameraCreate,
  CameraUpdate,
  EmailCheckResponse,
  LoginResponse,
  SessionResponse,
  User,
  UsernameCheckResponse
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
  username: string;
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

export async function updateAccount(payload: AccountUpdateInput): Promise<User> {
  return apiFetch<User>('/auth/account', {
    method: 'PUT',
    body: JSON.stringify(payload)
  });
}


export async function checkUsername(username: string): Promise<UsernameCheckResponse> {
  const params = new URLSearchParams({ username });
  return apiFetch<UsernameCheckResponse>(`/auth/check-username?${params.toString()}`);
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
