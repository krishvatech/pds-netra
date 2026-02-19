'use client';

import { useEffect, useRef, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { AppShell } from '@/components/layout/AppShell';
import { getSessionUser } from '@/lib/auth';
import type { AlertCueSettings } from '@/lib/alertCues';
import { DEFAULT_UI_PREFS, onUiPrefsChange, setUiPrefs, type UiPrefs } from '@/lib/uiPrefs';
import type { LoginResponse } from '@/lib/types';

export default function DashboardLayoutClient({
  children,
  initialBannerDismissed,
  initialUser,
  initialAlertCues,
  initialUiPrefs
}: {
  children: React.ReactNode;
  initialBannerDismissed: boolean;
  initialUser: LoginResponse['user'] | null;
  initialAlertCues: AlertCueSettings | null;
  initialUiPrefs: UiPrefs | null;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const isAuthPage = pathname === '/dashboard/login' || pathname === '/dashboard/register';
  const [authChecked, setAuthChecked] = useState(() => isAuthPage || Boolean(initialUser));
  const [authorized, setAuthorized] = useState(() => isAuthPage || Boolean(initialUser));
  const [user, setUser] = useState<LoginResponse['user'] | null>(initialUser);
  const [layoutPrefs, setLayoutPrefs] = useState<UiPrefs>(() => initialUiPrefs ?? DEFAULT_UI_PREFS);
  const contentRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (initialUiPrefs) {
      setUiPrefs(initialUiPrefs);
    }
  }, [initialUiPrefs]);

  useEffect(() => onUiPrefsChange(setLayoutPrefs), []);

  useEffect(() => {
    const prefersReduced =
      typeof window !== 'undefined' &&
      window.matchMedia &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    window.scrollTo({ top: 0, behavior: prefersReduced ? 'auto' : 'smooth' });
  }, [pathname]);

  useEffect(() => {
    let active = true;
    if (isAuthPage) {
      setAuthChecked(true);
      setAuthorized(true);
      return;
    }
    setAuthChecked(false);
    setAuthorized(false);
    (async () => {
      const user = await getSessionUser();
      if (!active) return;
      if (!user) {
        setAuthChecked(true);
        setAuthorized(false);
        setUser(null);
        router.replace('/dashboard/login');
        return;
      }
      setUser(user);
      setAuthorized(true);
      setAuthChecked(true);
    })();
    return () => {
      active = false;
    };
  }, [isAuthPage, router]);

  if (isAuthPage) return <>{children}</>;
  if (!authChecked) {
    return (
      <div className="app-shell flex min-h-screen items-center justify-center">
        <div className="text-sm uppercase tracking-[0.3em] text-slate-400">Checking session...</div>
      </div>
    );
  }
  if (!authorized) return null;

  return (
    <AppShell
      contentRef={contentRef}
      layoutPrefs={layoutPrefs}
      initialBannerDismissed={initialBannerDismissed}
      initialUser={user}
      initialAlertCues={initialAlertCues}
      initialUiPrefs={initialUiPrefs}
    >
      {children}
    </AppShell>
  );
}
