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
    <div className="app-shell">
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
      <div className="flex min-h-screen relative z-10">
        <Sidebar />
        <div className="flex-1">
          <StatusBanner />
          <Topbar />
          <div className="flex">
            <main className="min-w-0 flex-1 p-6 lg:p-8 pb-24 lg:pb-8 space-y-6 animate-fade-up">
              {children}
            </main>
            <LiveRail />
          </div>
        </div>
      </div>
      <MobileRail />
    </div>
  );
}
