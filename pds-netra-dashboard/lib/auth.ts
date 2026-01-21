import type { LoginResponse } from './types';

const TOKEN_KEY = 'pdsnetra_token';
const USER_KEY = 'pdsnetra_user';

export function setSession(resp: LoginResponse): void {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(TOKEN_KEY, resp.access_token);
  window.localStorage.setItem(USER_KEY, JSON.stringify(resp.user));
}

export function getToken(): string | null {
  if (typeof window === 'undefined') return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function getUser(): LoginResponse['user'] | null {
  if (typeof window === 'undefined') return null;
  const raw = window.localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as LoginResponse['user'];
  } catch {
    return null;
  }
}

export function clearSession(): void {
  if (typeof window === 'undefined') return;
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(USER_KEY);
}
