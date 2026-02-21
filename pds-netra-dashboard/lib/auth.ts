import type { LoginResponse } from './types';

const USER_KEY = 'pdsnetra_user';
const TOKEN_KEY = 'pdsnetra_token';
const USER_COOKIE = 'pdsnetra_user_snapshot';
const USER_COOKIE_MAX_AGE = 60 * 60 * 24 * 30;
const USER_COOKIE_MAX_BYTES = 1024;

function sanitizeUserCookiePayload(user: LoginResponse['user']): LoginResponse['user'] {
  return {
    id: user.id,
    username: user.username,
    name: user.name,
    role: user.role,
    district: user.district ?? null,
    godown_id: user.godown_id ?? null
  };
}

function setUserCookie(user: LoginResponse['user'] | null): void {
  if (typeof document === 'undefined') return;
  if (!user) {
    document.cookie = `${USER_COOKIE}=; path=/; max-age=0`;
    return;
  }
  const compact = sanitizeUserCookiePayload(user);
  const encoded = encodeURIComponent(JSON.stringify(compact));
  if (encoded.length > USER_COOKIE_MAX_BYTES) {
    document.cookie = `${USER_COOKIE}=; path=/; max-age=0`;
    return;
  }
  document.cookie = `${USER_COOKIE}=${encoded}; path=/; samesite=lax; max-age=${USER_COOKIE_MAX_AGE}`;
}

export function setSession(resp: LoginResponse): void {
  if (typeof window === 'undefined') return;
  if (resp?.user) window.localStorage.setItem(USER_KEY, JSON.stringify(resp.user));
  if (resp?.access_token) window.localStorage.setItem(TOKEN_KEY, String(resp.access_token));
  if (resp?.user) setUserCookie(resp.user);
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

export function getToken(): string | null {
  if (typeof window === 'undefined') return null;
  const token = window.localStorage.getItem(TOKEN_KEY);
  return token && token.trim() ? token : null;
}

export function clearSession(): void {
  if (typeof window === 'undefined') return;
  window.localStorage.removeItem(USER_KEY);
  window.localStorage.removeItem(TOKEN_KEY);
  setUserCookie(null);
}

export async function getSessionUser(): Promise<LoginResponse['user'] | null> {
  try {
    const resp = await fetch('/api/v1/auth/session', { method: 'GET', credentials: 'include', cache: 'no-store' });
    if (!resp.ok) {
      // Fallback for deployments where /api/v1/auth/session is routed to backend
      // instead of the Next.js proxy route.
      const user = getUser();
      const token = getToken();
      if (user && token) return user;
      clearSession();
      return null;
    }
    const data = (await resp.json()) as { user?: LoginResponse['user'] | null };
    if (data?.user) {
      window.localStorage.setItem(USER_KEY, JSON.stringify(data.user));
      setUserCookie(data.user);
      return data.user;
    }
    clearSession();
    return null;
  } catch {
    return getUser();
  }
}
