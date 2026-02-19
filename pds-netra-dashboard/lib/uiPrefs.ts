export type UiPrefs = {
  railOpen: boolean;
};

const KEY = 'pdsnetra-ui-prefs';
const PREFS_COOKIE = 'pdsnetra_ui_prefs';
const COOKIE_MAX_AGE = 60 * 60 * 24 * 30;

export const DEFAULT_UI_PREFS: UiPrefs = { railOpen: true };

export function getUiPrefs(): UiPrefs {
  if (typeof window === 'undefined') {
    return DEFAULT_UI_PREFS;
  }
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return DEFAULT_UI_PREFS;
    const parsed = JSON.parse(raw) as Partial<UiPrefs>;
    return {
      railOpen: parsed.railOpen !== false
    };
  } catch {
    return DEFAULT_UI_PREFS;
  }
}

export function setUiPrefs(next: UiPrefs): void {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(KEY, JSON.stringify(next));
  try {
    document.cookie = `${PREFS_COOKIE}=${encodeURIComponent(JSON.stringify(next))}; path=/; max-age=${COOKIE_MAX_AGE}`;
  } catch {
    // ignore cookie write errors
  }
  window.dispatchEvent(new CustomEvent('ui-prefs-changed', { detail: next }));
}

export function syncUiPrefsCookie(): void {
  if (typeof window === 'undefined') return;
  try {
    document.cookie = `${PREFS_COOKIE}=${encodeURIComponent(JSON.stringify(getUiPrefs()))}; path=/; max-age=${COOKIE_MAX_AGE}`;
  } catch {
    // ignore cookie write errors
  }
}

export function onUiPrefsChange(handler: (next: UiPrefs) => void): () => void {
  if (typeof window === 'undefined') return () => {};
  const listener = (event: Event) => {
    const detail = (event as CustomEvent<UiPrefs>).detail;
    if (detail) handler(detail);
  };
  window.addEventListener('ui-prefs-changed', listener);
  return () => window.removeEventListener('ui-prefs-changed', listener);
}
