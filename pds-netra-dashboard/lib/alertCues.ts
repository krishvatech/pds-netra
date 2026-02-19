import { getUser } from './auth';

export type AlertCueSettings = {
  sound: boolean;
  visual: boolean;
  minSeverity: 'info' | 'warning' | 'critical';
  quietHoursEnabled: boolean;
  quietHoursStart: string;
  quietHoursEnd: string;
};

export const DEFAULT_ALERT_CUES: AlertCueSettings = {
  sound: false,
  visual: true,
  minSeverity: 'warning',
  quietHoursEnabled: false,
  quietHoursStart: '22:00',
  quietHoursEnd: '06:00'
};

const KEY = 'pdsnetra-alert-cues';
const PROFILE_KEY = 'pdsnetra-alert-profile';
const CUES_COOKIE = 'pdsnetra_alert_cues';
const PROFILE_COOKIE = 'pdsnetra_alert_profile';
const COOKIE_MAX_AGE = 60 * 60 * 24 * 30;

function setCookie(name: string, value: string): void {
  if (typeof document === 'undefined') return;
  document.cookie = `${name}=${encodeURIComponent(value)}; path=/; max-age=${COOKIE_MAX_AGE}`;
}

function resolveKey(): string {
  if (typeof window === 'undefined') return KEY;
  const profile = window.localStorage.getItem(PROFILE_KEY);
  if (profile) return `${KEY}:${profile}`;
  const user = getUser();
  const identifier = user?.username || user?.name || 'default';
  return `${KEY}:${identifier}`;
}

export function getAlertProfile(): string {
  if (typeof window === 'undefined') return 'default';
  return window.localStorage.getItem(PROFILE_KEY) || 'default';
}

export function setAlertProfile(profile: string): void {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(PROFILE_KEY, profile);
  setCookie(PROFILE_COOKIE, profile);
  try {
    setCookie(CUES_COOKIE, JSON.stringify(getAlertCues()));
  } catch {
    // ignore cookie write errors
  }
  window.dispatchEvent(new CustomEvent('alert-cues-changed', { detail: getAlertCues() }));
}

export function getAlertCues(): AlertCueSettings {
  if (typeof window === 'undefined') {
    return DEFAULT_ALERT_CUES;
  }
  try {
    const raw = window.localStorage.getItem(resolveKey());
    if (!raw) {
      return DEFAULT_ALERT_CUES;
    }
    const parsed = JSON.parse(raw) as Partial<AlertCueSettings>;
    return {
      sound: Boolean(parsed.sound),
      visual: parsed.visual !== false,
      minSeverity: parsed.minSeverity ?? 'warning',
      quietHoursEnabled: Boolean(parsed.quietHoursEnabled),
      quietHoursStart: parsed.quietHoursStart ?? '22:00',
      quietHoursEnd: parsed.quietHoursEnd ?? '06:00'
    };
  } catch {
    return DEFAULT_ALERT_CUES;
  }
}

export function setAlertCues(next: AlertCueSettings): void {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(resolveKey(), JSON.stringify(next));
  try {
    setCookie(CUES_COOKIE, JSON.stringify(next));
  } catch {
    // ignore cookie write errors
  }
  window.dispatchEvent(new CustomEvent('alert-cues-changed', { detail: next }));
}

export function syncAlertCuesCookie(): void {
  if (typeof window === 'undefined') return;
  try {
    setCookie(CUES_COOKIE, JSON.stringify(getAlertCues()));
  } catch {
    // ignore cookie write errors
  }
}

export function onAlertCuesChange(handler: (next: AlertCueSettings) => void): () => void {
  if (typeof window === 'undefined') return () => {};
  const listener = (event: Event) => {
    const detail = (event as CustomEvent<AlertCueSettings>).detail;
    if (detail) handler(detail);
  };
  window.addEventListener('alert-cues-changed', listener);
  return () => window.removeEventListener('alert-cues-changed', listener);
}
