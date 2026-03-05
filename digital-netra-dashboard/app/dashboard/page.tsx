'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { BrandLogo } from '@/components/ui/brand-logo';
import { logout } from '@/lib/api';
import { getSessionUser, getUser } from '@/lib/auth';
import type { User } from '@/lib/types';

export default function DashboardPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    async function hydrate() {
      setMounted(true);
      const cached = getUser();
      if (cached) setUser(cached);
      const sessionUser = await getSessionUser();
      if (!sessionUser) {
        router.replace('/auth/login');
        return;
      }
      setUser(sessionUser);
    }
    hydrate();
  }, [router]);

  async function handleLogout() {
    await logout();
    router.replace('/auth/login');
  }

  return (
    <div className="relative min-h-screen overflow-hidden bg-[#0b1020]">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(1200px_circle_at_15%_12%,rgba(255,255,255,0.12),rgba(9,15,30,0.85)_45%,rgba(6,10,20,0.98)_70%)]" />
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(1000px_circle_at_85%_5%,rgba(120,170,255,0.22),rgba(7,12,25,0.0)_35%)]" />
      <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(180deg,rgba(15,23,42,0.15),rgba(2,6,23,0.9))]" />

      <main className="relative z-10 flex min-h-screen items-center justify-center px-6 py-12">
        <div className="w-full max-w-xl rounded-2xl border border-white/15 bg-white/10 p-8 shadow-[0_28px_70px_-50px_rgba(2,6,23,0.9)] backdrop-blur-xl">
          <div className="flex flex-col items-center gap-4 text-center">
            <BrandLogo className="h-24 w-auto" />
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.35em] text-slate-300/80">Dashboard</p>
              <h1 className="mt-2 text-2xl font-display text-slate-100 sm:text-3xl">Welcome{user?.first_name ? `, ${user.first_name}` : ''}</h1>
              <p className="mt-2 text-sm text-slate-400">You are signed in to Digital Netra.</p>
            </div>
          </div>

          <div className="mt-6 rounded-xl border border-white/10 bg-white/5 p-4 text-sm text-slate-300">
            <div className="flex items-center justify-between">
              <span className="text-slate-400">Email</span>
              <span>{mounted ? user?.email ?? '—' : '—'}</span>
            </div>
            <div className="mt-2 flex items-center justify-between">
              <span className="text-slate-400">Role</span>
              <span>{mounted ? (user?.is_admin ? 'Admin' : 'User') : '—'}</span>
            </div>
          </div>

          <button
            onClick={handleLogout}
            className="btn-primary mt-6 w-full rounded-full py-2.5 text-sm font-semibold"
          >
            Logout
          </button>
        </div>
      </main>
    </div>
  );
}
