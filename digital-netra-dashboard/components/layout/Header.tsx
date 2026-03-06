'use client';

import { useEffect, useRef, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import Image from 'next/image';
import Link from 'next/link';
import { LogOut, Menu, Settings, User } from 'lucide-react';
import { logout } from '@/lib/api';
import { getUser } from '@/lib/auth';
import type { User as UserType } from '@/lib/types';
import { getNavItems } from '@/components/layout/nav-items';

export function Header() {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<UserType | null>(null);
  const [profileOpen, setProfileOpen] = useState(false);
  const [navOpen, setNavOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);
  const navItems = getNavItems(Boolean(user?.is_admin));

  useEffect(() => {
    setUser(getUser());
  }, []);

  useEffect(() => {
    function handleClick(event: MouseEvent) {
      if (!menuRef.current) return;
      if (!menuRef.current.contains(event.target as Node)) {
        setProfileOpen(false);
      }
    }
    if (profileOpen) {
      document.addEventListener('mousedown', handleClick);
    }
    return () => document.removeEventListener('mousedown', handleClick);
  }, [profileOpen]);

  useEffect(() => {
    document.body.style.overflow = navOpen ? 'hidden' : '';
    return () => {
      document.body.style.overflow = '';
    };
  }, [navOpen]);

  async function handleLogout() {
    await logout();
    router.replace('/auth/login');
  }

  return (
    <header className="relative z-30 flex items-center justify-between border-b border-white/10 bg-slate-900/70 px-6 py-4 backdrop-blur">
      <div className="flex items-center gap-3">
        <button
          type="button"
          aria-label="Open navigation"
          className="flex h-10 w-10 items-center justify-center rounded-full border border-white/10 bg-white/5 text-slate-200 hover:border-white/20 hover:bg-white/10 lg:hidden"
          onClick={() => setNavOpen(true)}
        >
          <Menu size={16} />
        </button>
        <Image src="/krishvatech-logo.png" alt="Krishvatech" width={48} height={48} className="h-10 w-10" />
        <div>
          <div className="text-[11px] uppercase tracking-[0.4em] text-slate-400">Control Deck</div>
          <div className="text-xl font-semibold text-slate-100 sm:text-2xl">Digital Netra Dashboard</div>
        </div>
      </div>

      <div className="relative" ref={menuRef}>
        <button
          type="button"
          onClick={() => setProfileOpen((prev) => !prev)}
          className="flex h-10 w-10 items-center justify-center rounded-full border border-white/10 bg-white/5 text-slate-200 hover:border-white/20 hover:bg-white/10"
          aria-label="Open profile menu"
        >
          <User size={16} />
        </button>

        {profileOpen && (
          <div className="absolute right-0 mt-3 w-56 overflow-hidden rounded-2xl border border-white/10 bg-slate-950/90 shadow-[0_20px_50px_-30px_rgba(2,6,23,0.9)] backdrop-blur z-50">
            <div className="border-b border-white/10 px-4 py-3">
              <div className="text-xs uppercase tracking-[0.3em] text-slate-500">Signed in</div>
              <div className="mt-1 text-sm font-semibold text-slate-100">
                {user?.first_name ? `${user.first_name} ${user.last_name ?? ''}`.trim() : 'Operator'}
              </div>
              <div className="text-xs text-slate-400">{user?.email ?? 'user@digitalnetra.ai'}</div>
            </div>
            <div className="flex flex-col p-2 text-sm">
              <Link
                href="/dashboard/account"
                className="flex items-center gap-2 rounded-xl px-3 py-2 text-slate-200 hover:bg-white/10"
                onClick={() => setProfileOpen(false)}
              >
                <Settings size={14} className="text-slate-400" />
                Account settings
              </Link>
              <button
                type="button"
                onClick={handleLogout}
                className="flex items-center gap-2 rounded-xl px-3 py-2 text-slate-200 hover:bg-white/10"
              >
                <LogOut size={14} className="text-slate-400" />
                Logout
              </button>
            </div>
          </div>
        )}
      </div>

      {navOpen && (
        <div
          className="fixed inset-0 z-50 bg-slate-950/85 backdrop-blur-md lg:hidden"
          onClick={() => setNavOpen(false)}
        >
          <aside
            className="absolute left-0 top-0 h-full w-72 max-w-[86vw] border-r border-white/10 bg-slate-900/95 px-5 py-6 shadow-2xl"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex items-center justify-between gap-3">
              <div className="space-y-1">
                <div className="text-xs uppercase tracking-[0.3em] text-slate-500">Digital Netra</div>
                <div className="text-xl font-semibold text-slate-100">Operations Desk</div>
              </div>
              <button
                type="button"
                aria-label="Close navigation"
                className="flex h-9 w-9 items-center justify-center rounded-full border border-white/10 bg-white/5 text-slate-300 hover:border-white/30 hover:text-slate-100"
                onClick={() => setNavOpen(false)}
              >
                <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M18 6 6 18M6 6l12 12" />
                </svg>
              </button>
            </div>

            <nav className="mt-8 space-y-2 overflow-y-auto pr-1">
              {navItems.map((item) => {
                const isActive = pathname === item.href;
                const Icon = item.icon;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={[
                      'flex items-center justify-between rounded-2xl px-4 py-3 text-sm transition',
                      isActive
                        ? 'border border-white/15 bg-white/10 font-semibold text-white'
                        : 'border border-white/10 bg-white/5 text-slate-200 hover:border-white/20 hover:bg-white/10'
                    ].join(' ')}
                    onClick={() => setNavOpen(false)}
                  >
                    <span className="flex items-center gap-3">
                      <Icon size={16} />
                      {item.label}
                    </span>
                    {isActive && <span className="h-2 w-2 rounded-full bg-amber-400" />}
                  </Link>
                );
              })}
            </nav>
          </aside>
        </div>
      )}
    </header>
  );
}
