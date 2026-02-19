'use client';

import { useEffect, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { Sidebar } from '@/components/layout/Sidebar';
import { Topbar } from '@/components/layout/Topbar';
import { LiveRail, MobileRail } from '@/components/layout/LiveRail';
import { StatusBanner } from '@/components/layout/StatusBanner';
import { getSessionUser } from '@/lib/auth';

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const isAuthPage = pathname === '/dashboard/login' || pathname === '/dashboard/register';
  const [authChecked, setAuthChecked] = useState(false);
  const [authorized, setAuthorized] = useState(false);

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
        router.replace('/dashboard/login');
        return;
      }
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
    <div className="app-shell flex min-h-screen flex-col overflow-x-hidden [--header-stack-h:128px] md:[--header-stack-h:140px]">
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
      <div className="fixed top-0 left-0 right-0 z-50 bg-slate-950/90 backdrop-blur-xl border-b border-white/5">
        <StatusBanner />
        <Topbar />
      </div>
      <div className="relative z-10 flex flex-1 w-full overflow-hidden pt-[var(--header-stack-h)]">
        <Sidebar />
        <div className="min-w-0 flex-1 flex flex-col min-h-0">
          <div className="flex min-h-0 flex-1 overflow-hidden">
            <div className="flex-1 overflow-y-auto scroll-pt-[var(--header-stack-h)]">
              <div className="grid w-full min-w-0 gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
                <main className="animate-fade-up flex-1 min-w-0 space-y-4 md:space-y-6 px-4 py-4 md:px-6 md:py-6 lg:px-8 lg:py-8 [&>*]:min-w-0">
                  <MobileRail />
                  {children}
                </main>
                <LiveRail />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
