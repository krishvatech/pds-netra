export type UiPrefs = {
  railOpen: boolean;
};

const KEY = 'pdsnetra-ui-prefs';

export function getUiPrefs(): UiPrefs {
  if (typeof window === 'undefined') {
    return { railOpen: true };
  }
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return { railOpen: true };
    const parsed = JSON.parse(raw) as Partial<UiPrefs>;
    return {
      railOpen: parsed.railOpen !== false
    };
  } catch {
    return { railOpen: true };
  }
}

export function setUiPrefs(next: UiPrefs): void {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(KEY, JSON.stringify(next));
  window.dispatchEvent(new CustomEvent('ui-prefs-changed', { detail: next }));
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
