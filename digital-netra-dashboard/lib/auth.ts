import type { LoginResponse, User } from '@/lib/types';

const TOKEN_KEY = 'dn_token';
const USER_KEY = 'dn_user';

export function setSession(payload: LoginResponse) {
  if (typeof window === 'undefined') return;
  localStorage.setItem(TOKEN_KEY, payload.access_token);
  localStorage.setItem(USER_KEY, JSON.stringify(payload.user));
}

export function getToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function getUser(): User | null {
  if (typeof window === 'undefined') return null;
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as User;
  } catch {
    return null;
  }
}

export function setUser(user: User) {
  if (typeof window === 'undefined') return;
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearSession() {
  if (typeof window === 'undefined') return;
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

export async function getSessionUser(): Promise<User | null> {
  if (typeof window === 'undefined') return null;
  const resp = await fetch('/api/v1/auth/account', { credentials: 'include' });
  if (!resp.ok) return null;
  const data = await resp.json();
  const user = (data?.user || data || null) as User | null;
  if (user) {
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  }
  return user;
}
