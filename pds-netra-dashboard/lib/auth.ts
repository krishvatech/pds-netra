import type { LoginResponse } from './types';

const USER_KEY = 'pdsnetra_user';

export function setSession(resp: LoginResponse): void {
  if (typeof window === 'undefined') return;
  if (resp?.user) window.localStorage.setItem(USER_KEY, JSON.stringify(resp.user));
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
  window.localStorage.removeItem(USER_KEY);
}

export async function getSessionUser(): Promise<LoginResponse['user'] | null> {
  try {
    const resp = await fetch('/api/v1/auth/session', { method: 'GET', credentials: 'include', cache: 'no-store' });
    if (!resp.ok) {
      clearSession();
      return null;
    }
    const data = (await resp.json()) as { user?: LoginResponse['user'] | null };
    if (data?.user) {
      window.localStorage.setItem(USER_KEY, JSON.stringify(data.user));
      return data.user;
    }
    clearSession();
    return null;
  } catch {
    return getUser();
  }
}
