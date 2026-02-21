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
    <div className="app-shell min-h-screen grid grid-rows-[auto_minmax(0,1fr)]">
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

      <header className="sticky top-0 z-[60] bg-slate-950/90 backdrop-blur border-b border-white/10">
        <StatusBanner initialDismissed={initialBannerDismissed} />
        <Topbar user={initialUser} initialAlertCues={initialAlertCues} initialUiPrefs={initialUiPrefs} />
      </header>

      <div className="relative z-10 min-h-0 w-full overflow-hidden">
        <div className="grid min-h-0 w-full grid-cols-1 lg:grid-cols-[260px_minmax(0,1fr)]">
          <Sidebar user={initialUser} />
          <div className="min-h-0 min-w-0">
            <div
              className={`grid min-h-0 w-full ${layoutPrefs.railOpen ? 'lg:grid-cols-[minmax(0,1fr)_360px]' : 'lg:grid-cols-1'
                }`}
            >
              <main
                ref={contentRef}
                className="min-h-0 min-w-0 space-y-4 md:space-y-6 px-4 pb-4 md:px-6 md:pb-6 lg:px-8 lg:pb-8 [&>*]:min-w-0"
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
    </div>
  );
}
