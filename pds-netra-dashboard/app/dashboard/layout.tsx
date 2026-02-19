import { cookies } from 'next/headers';
import type { AlertCueSettings } from '@/lib/alertCues';
import { DEFAULT_UI_PREFS, type UiPrefs } from '@/lib/uiPrefs';
import type { LoginResponse } from '@/lib/types';
import DashboardLayoutClient from './DashboardLayoutClient';

const DISMISS_COOKIE = 'pds_banner_dismissed';
const USER_COOKIE = 'pdsnetra_user_snapshot';
const ALERT_CUES_COOKIE = 'pdsnetra_alert_cues';
const UI_PREFS_COOKIE = 'pdsnetra_ui_prefs';

export default async function DashboardLayout({ children }: { children: React.ReactNode }) {
  const cookieStore = await cookies();
  const initialBannerDismissed = cookieStore.get(DISMISS_COOKIE)?.value === '1';
  const userCookie = cookieStore.get(USER_COOKIE)?.value;
  const cuesCookie = cookieStore.get(ALERT_CUES_COOKIE)?.value;
  const uiPrefsCookie = cookieStore.get(UI_PREFS_COOKIE)?.value;
  let initialUser: LoginResponse['user'] | null = null;
  let initialAlertCues: AlertCueSettings | null = null;
  let initialUiPrefs: UiPrefs = DEFAULT_UI_PREFS;
  if (userCookie) {
    try {
      initialUser = JSON.parse(decodeURIComponent(userCookie)) as LoginResponse['user'];
    } catch {
      initialUser = null;
    }
  }
  if (cuesCookie) {
    try {
      initialAlertCues = JSON.parse(decodeURIComponent(cuesCookie)) as AlertCueSettings;
    } catch {
      initialAlertCues = null;
    }
  }
  if (uiPrefsCookie) {
    try {
      initialUiPrefs = JSON.parse(decodeURIComponent(uiPrefsCookie)) as UiPrefs;
    } catch {
      initialUiPrefs = DEFAULT_UI_PREFS;
    }
  }

  return (
    <DashboardLayoutClient
      initialBannerDismissed={initialBannerDismissed}
      initialUser={initialUser}
      initialAlertCues={initialAlertCues}
      initialUiPrefs={initialUiPrefs}
    >
      {children}
    </DashboardLayoutClient>
  );
}
