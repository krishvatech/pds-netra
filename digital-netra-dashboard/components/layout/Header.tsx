'use client';

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import Image from 'next/image';
import Link from 'next/link';
import { LogOut, Settings, User } from 'lucide-react';
import { logout } from '@/lib/api';
import { getUser } from '@/lib/auth';
import type { User as UserType } from '@/lib/types';

export function Header() {
  const router = useRouter();
  const [user, setUser] = useState<UserType | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setUser(getUser());
  }, []);

  useEffect(() => {
    function handleClick(event: MouseEvent) {
      if (!menuRef.current) return;
      if (!menuRef.current.contains(event.target as Node)) {
        setMenuOpen(false);
      }
    }
    if (menuOpen) {
      document.addEventListener('mousedown', handleClick);
    }
    return () => document.removeEventListener('mousedown', handleClick);
  }, [menuOpen]);

  async function handleLogout() {
    await logout();
    router.replace('/auth/login');
  }

  return (
    <header className="relative z-30 flex items-center justify-between border-b border-white/10 bg-slate-900/70 px-6 py-4 backdrop-blur">
      <div className="flex items-center gap-3">
        <Image src="/krishvatech-logo.png" alt="Krishvatech" width={48} height={48} className="h-10 w-10" />
        <div>
          <div className="text-[11px] uppercase tracking-[0.4em] text-slate-400">Control Deck</div>
          <div className="text-xl font-semibold text-slate-100 sm:text-2xl">Digital Netra Dashboard</div>
        </div>
      </div>

      <div className="relative" ref={menuRef}>
        <button
          type="button"
          onClick={() => setMenuOpen((prev) => !prev)}
          className="flex h-10 w-10 items-center justify-center rounded-full border border-white/10 bg-white/5 text-slate-200 hover:border-white/20 hover:bg-white/10"
          aria-label="Open profile menu"
        >
          <User size={16} />
        </button>

        {menuOpen && (
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
                onClick={() => setMenuOpen(false)}
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
    </header>
  );
}
