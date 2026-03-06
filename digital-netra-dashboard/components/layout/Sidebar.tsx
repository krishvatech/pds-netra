'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { getNavItems } from '@/components/layout/nav-items';
import { getUser } from '@/lib/auth';
import type { User as UserType } from '@/lib/types';

export function Sidebar() {
  const pathname = usePathname();
  const [user, setUser] = useState<UserType | null>(null);

  useEffect(() => {
    setUser(getUser());
  }, []);

  const items = useMemo(() => getNavItems(Boolean(user?.is_admin)), [user]);

  return (
    <aside className="hidden h-full min-h-0 w-[240px] flex-col border-r border-white/10 bg-slate-900/70 px-5 py-6 backdrop-blur lg:flex">
      <div className="space-y-1">
        <div className="text-xs uppercase tracking-[0.3em] text-slate-500">Digital Netra</div>
        <div className="text-xl font-semibold text-slate-100">Operations Desk</div>
      </div>

      <nav className="mt-8 space-y-2">
        {items.map((item) => {
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
                  : 'border border-white/5 bg-white/5 text-slate-300 hover:border-white/10 hover:bg-white/10'
              ].join(' ')}
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

      <div className="mt-auto rounded-2xl border border-white/10 bg-white/5 p-4 text-xs text-slate-400">
        <div className="text-slate-200">Digital Netra</div>
        <div className="mt-2">Version 1.0 · Static UI</div>
      </div>
    </aside>
  );
}
