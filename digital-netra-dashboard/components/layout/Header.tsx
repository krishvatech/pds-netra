'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { LogOut, User } from 'lucide-react';
import { BrandLogo } from '@/components/ui/brand-logo';
import { logout } from '@/lib/api';
import { getUser } from '@/lib/auth';
import type { User as UserType } from '@/lib/types';

export function Header() {
  const router = useRouter();
  const [user, setUser] = useState<UserType | null>(null);

  useEffect(() => {
    setUser(getUser());
  }, []);

  async function handleLogout() {
    await logout();
    router.replace('/auth/login');
  }

  return (
    <header className="flex items-center justify-between border-b border-white/10 bg-slate-900/70 px-6 py-4 backdrop-blur">
      <div className="flex items-center gap-3">
        <BrandLogo className="h-10 w-auto" />
        <div>
          <div className="text-[11px] uppercase tracking-[0.35em] text-slate-400">Digital Netra</div>
          <div className="text-base font-semibold text-slate-100">Operations</div>
        </div>
      </div>

      <div className="flex items-center gap-4">
        <div className="hidden items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 md:flex">
          <User size={14} className="text-slate-400" />
          <span>{user?.first_name ? `${user.first_name} ${user.last_name ?? ''}`.trim() : 'Operator'}</span>
        </div>
        <button
          onClick={handleLogout}
          className="btn-primary flex items-center gap-2 rounded-full px-4 py-2 text-xs font-semibold"
        >
          <LogOut size={14} />
          Logout
        </button>
      </div>
    </header>
  );
}
