import { getUser } from './auth';

export type AlertCueSettings = {
  sound: boolean;
  visual: boolean;
  minSeverity: 'info' | 'warning' | 'critical';
  quietHoursEnabled: boolean;
  quietHoursStart: string;
  quietHoursEnd: string;
};

const KEY = 'pdsnetra-alert-cues';
const PROFILE_KEY = 'pdsnetra-alert-profile';

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
  window.dispatchEvent(new CustomEvent('alert-cues-changed', { detail: getAlertCues() }));
}

export function getAlertCues(): AlertCueSettings {
  if (typeof window === 'undefined') {
    return {
      sound: false,
      visual: true,
      minSeverity: 'warning',
      quietHoursEnabled: false,
      quietHoursStart: '22:00',
      quietHoursEnd: '06:00'
    };
  }
  try {
    const raw = window.localStorage.getItem(resolveKey());
    if (!raw) {
      return {
        sound: false,
        visual: true,
        minSeverity: 'warning',
        quietHoursEnabled: false,
        quietHoursStart: '22:00',
        quietHoursEnd: '06:00'
      };
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
    return {
      sound: false,
      visual: true,
      minSeverity: 'warning',
      quietHoursEnabled: false,
      quietHoursStart: '22:00',
      quietHoursEnd: '06:00'
    };
  }
}

export function setAlertCues(next: AlertCueSettings): void {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(resolveKey(), JSON.stringify(next));
  window.dispatchEvent(new CustomEvent('alert-cues-changed', { detail: next }));
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
