'use client';

import { useEffect } from 'react';
import type { ReactNode, RefObject } from 'react';
import { Sidebar } from '@/components/layout/Sidebar';
import { Topbar } from '@/components/layout/Topbar';
import { LiveRail, MobileRail } from '@/components/layout/LiveRail';
import { StatusBanner } from '@/components/layout/StatusBanner';
import { DEFAULT_UI_PREFS, getUiPrefs, setUiPrefs, type UiPrefs } from '@/lib/uiPrefs';
import type { AlertCueSettings } from '@/lib/alertCues';
import type { LoginResponse } from '@/lib/types';

type AppShellProps = {
  children: ReactNode;
  contentRef?: RefObject<HTMLDivElement>;
  layoutPrefs: UiPrefs;
  initialBannerDismissed: boolean;
  initialUser: LoginResponse['user'] | null;
  initialAlertCues: AlertCueSettings | null;
  initialUiPrefs: UiPrefs | null;
};

export function AppShell({
  children,
  contentRef,
  layoutPrefs,
  initialBannerDismissed,
  initialUser,
  initialAlertCues,
  initialUiPrefs
}: AppShellProps) {
  useEffect(() => {
    const checkWidth = () => {
      if (window.innerWidth < 1024 && getUiPrefs().railOpen) {
        setUiPrefs({ railOpen: false });
      }
    };
    checkWidth();

    let debounceTimer: ReturnType<typeof setTimeout>;
    const handleResize = () => {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(checkWidth, 100);
    };
    window.addEventListener('resize', handleResize);
    return () => {
      clearTimeout(debounceTimer);
      window.removeEventListener('resize', handleResize);
    };
  }, []);

  return (
    <div className="app-shell h-[100dvh] w-full flex flex-col overflow-hidden">
      <div className="pointer-events-none absolute inset-0" aria-hidden>
        <div className="app-bg" />
        <div className="app-grid" />
        <div className="app-scanlines" />
        <div className="pointer-events-none absolute -top-24 right-12 h-64 w-64 rounded-full bg-gradient-to-br from-amber-400/40 via-orange-400/30 to-transparent blur-3xl animate-float" />
        <div className="pointer-events-none absolute bottom-[-120px] left-[-80px] h-72 w-72 rounded-full bg-gradient-to-tr from-sky-400/40 via-blue-400/30 to-transparent blur-3xl animate-float" />
        <div className="radar-wrap">
          <div className="radar-sweep" />
          <div className="radar-ring" />
          <div className="radar-grid" />
        </div>
      </div>

      <header className="flex-none relative z-[60] bg-slate-950/90 backdrop-blur border-b border-white/10">
        <StatusBanner initialDismissed={initialBannerDismissed} />
        <Topbar user={initialUser} initialAlertCues={initialAlertCues} initialUiPrefs={initialUiPrefs} />
      </header>

      <div className="flex-1 flex min-h-0 w-full relative z-10 overflow-hidden">
        <Sidebar user={initialUser} />

        <div className="flex-1 flex flex-col min-w-0 h-full overflow-hidden">
          <div className={`flex-1 flex h-full min-h-0 w-full ${layoutPrefs.railOpen ? 'flex-col lg:flex-row' : 'flex-col'}`}>
            <main
              ref={contentRef}
              className="flex-1 h-full overflow-y-auto min-w-0 space-y-4 md:space-y-6 px-4 pb-4 md:px-6 md:pb-6 lg:px-8 lg:pb-8 [&>*]:min-w-0"
            >
              <MobileRail
                initialUiPrefs={initialUiPrefs ?? DEFAULT_UI_PREFS}
                initialAlertCues={initialAlertCues}
              />
              {children}
            </main>

            <LiveRail
              initialUiPrefs={initialUiPrefs ?? DEFAULT_UI_PREFS}
              initialAlertCues={initialAlertCues}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
