'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import type { ReactNode } from 'react';

const tabs = [
  { href: '/dashboard/anpr', label: 'Live / Sessions' },
  { href: '/dashboard/anpr/vehicles', label: 'Vehicles' },
  { href: '/dashboard/anpr/daily-plan', label: 'Daily Plan' },
  { href: '/dashboard/anpr/reports', label: 'Reports' },
];

export default function AnprLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        {tabs.map((t) => {
          const active = pathname === t.href;
          return (
            <Link
              key={t.href}
              href={t.href}
              className={`rounded-xl px-3 py-2 text-sm border transition ${
                active
                  ? 'bg-white/10 border-white/20 text-white font-semibold'
                  : 'bg-white/5 border-white/10 text-slate-200 hover:bg-white/10'
              }`}
            >
              {t.label}
            </Link>
          );
        })}
      </div>
      {children}
    </div>
  );
}
