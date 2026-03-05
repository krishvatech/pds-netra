import { clearSession, getToken } from '@/lib/auth';
import type {
  EmailCheckResponse,
  LoginResponse,
  SessionResponse,
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
  email: string;
  phone?: string;
  password: string;
  confirm_password: string;
};

export type LoginInput = {
  email: string;
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

export async function checkUsername(username: string): Promise<UsernameCheckResponse> {
  const params = new URLSearchParams({ username });
  return apiFetch<UsernameCheckResponse>(`/auth/check-username?${params.toString()}`);
}

export async function checkEmail(email: string): Promise<EmailCheckResponse> {
  const params = new URLSearchParams({ email });
  return apiFetch<EmailCheckResponse>(`/auth/check-email?${params.toString()}`);
}
