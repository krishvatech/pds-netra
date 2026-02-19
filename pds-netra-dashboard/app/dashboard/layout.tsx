'use client';

import { useEffect, useLayoutEffect, useRef, useState } from 'react';
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
  const shellRef = useRef<HTMLDivElement | null>(null);
  const topbarRef = useRef<HTMLDivElement | null>(null);
  const bannerHeightRef = useRef(0);
  const topbarHeightRef = useRef(0);
  const safetyGapRef = useRef(6);

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

  useLayoutEffect(() => {
    if (!shellRef.current || !topbarRef.current) return;
    const shell = shellRef.current;
    const updateStackHeight = () => {
      const total = bannerHeightRef.current + topbarHeightRef.current + safetyGapRef.current;
      shell.style.setProperty('--header-stack-h', `${total}px`);
    };
    const measureTopbar = () => {
      topbarHeightRef.current = Math.round(topbarRef.current?.getBoundingClientRect().height || 0);
      updateStackHeight();
    };
    measureTopbar();
    const observer = new ResizeObserver(measureTopbar);
    observer.observe(topbarRef.current);
    window.addEventListener('resize', measureTopbar);
    const rafIds: number[] = [];
    for (let i = 0; i < 5; i += 1) {
      rafIds.push(requestAnimationFrame(measureTopbar));
    }
    const timeoutIds = [
      window.setTimeout(measureTopbar, 150),
      window.setTimeout(measureTopbar, 600)
    ];
    return () => {
      observer.disconnect();
      window.removeEventListener('resize', measureTopbar);
      rafIds.forEach((id) => cancelAnimationFrame(id));
      timeoutIds.forEach((id) => window.clearTimeout(id));
    };
  }, []);

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
    <div
      ref={shellRef}
      className="app-shell flex min-h-screen flex-col overflow-x-hidden [--header-stack-h:128px] md:[--header-stack-h:140px]"
    >
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
        <StatusBanner
          onHeightChange={(height) => {
            bannerHeightRef.current = height;
            if (!shellRef.current) return;
            const total = bannerHeightRef.current + topbarHeightRef.current + safetyGapRef.current;
            shellRef.current.style.setProperty('--header-stack-h', `${total}px`);
          }}
        />
        <div ref={topbarRef}>
          <Topbar />
        </div>
      </div>
      <div className="relative z-10 flex flex-1 w-full overflow-hidden pt-[var(--header-stack-h)]">
        <Sidebar />
        <div className="min-w-0 flex-1 flex flex-col min-h-0">
          <div className="flex min-h-0 flex-1 overflow-hidden">
            <div className="flex-1 overflow-y-auto scroll-pt-[var(--header-stack-h)]">
              <div className="grid w-full min-w-0 gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
                <main className="animate-fade-up flex-1 min-w-0 space-y-4 md:space-y-6 px-4 pb-4 pt-18 md:px-6 md:pb-6 md:pt-20 lg:px-8 lg:pb-8 lg:pt-22 [&>*]:min-w-0">
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
