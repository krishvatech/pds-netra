'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';
import { getAlertProfile, onAlertCuesChange } from '@/lib/alertCues';

const nav = [
  { href: '/dashboard/overview', label: 'Overview', icon: OverviewIcon },
  { href: '/dashboard/godowns', label: 'Godowns', icon: WarehouseIcon },
  { href: '/dashboard/alerts', label: 'Alerts', icon: AlertIcon },
  { href: '/dashboard/health', label: 'Health', icon: HeartbeatIcon },
  { href: '/dashboard/live', label: 'Live Cameras', icon: LiveIcon },
  { href: '/dashboard/test-runs', label: 'Test Runs', icon: TestRunIcon }
];

function OverviewIcon({ active }: { active: boolean }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M4 13.5L10 7.5L13 10.5L20 4"
        stroke={active ? '#f59e0b' : '#64748b'}
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M4 20H20"
        stroke={active ? '#f59e0b' : '#64748b'}
        strokeWidth="1.6"
        strokeLinecap="round"
      />
    </svg>
  );
}

function WarehouseIcon({ active }: { active: boolean }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M3 10.5L12 4L21 10.5"
        stroke={active ? '#f59e0b' : '#64748b'}
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M5 10.5V20H19V10.5"
        stroke={active ? '#f59e0b' : '#64748b'}
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M9 20V14H15V20"
        stroke={active ? '#f59e0b' : '#64748b'}
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function AlertIcon({ active }: { active: boolean }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M12 7V13"
        stroke={active ? '#f59e0b' : '#64748b'}
        strokeWidth="1.8"
        strokeLinecap="round"
      />
      <circle cx="12" cy="17" r="1.2" fill={active ? '#f59e0b' : '#64748b'} />
      <path
        d="M5.5 19.5H18.5L12 5.5L5.5 19.5Z"
        stroke={active ? '#f59e0b' : '#64748b'}
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function HeartbeatIcon({ active }: { active: boolean }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M3 12H7L9.5 6L13.5 18L16.5 12H21"
        stroke={active ? '#f59e0b' : '#64748b'}
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function TestRunIcon({ active }: { active: boolean }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M6 4H14L18 8V20H6V4Z"
        stroke={active ? '#f59e0b' : '#64748b'}
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <path
        d="M14 4V8H18"
        stroke={active ? '#f59e0b' : '#64748b'}
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <path
        d="M8 13H16"
        stroke={active ? '#f59e0b' : '#64748b'}
        strokeWidth="1.6"
        strokeLinecap="round"
      />
      <path
        d="M8 17H14"
        stroke={active ? '#f59e0b' : '#64748b'}
        strokeWidth="1.6"
        strokeLinecap="round"
      />
    </svg>
  );
}

function LiveIcon({ active }: { active: boolean }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
      <rect
        x="3"
        y="5"
        width="18"
        height="14"
        rx="2"
        stroke={active ? '#f59e0b' : '#64748b'}
        strokeWidth="1.6"
      />
      <circle cx="17.5" cy="9" r="2" fill={active ? '#f59e0b' : '#64748b'} />
      <path
        d="M7 9H12M7 12H14"
        stroke={active ? '#f59e0b' : '#64748b'}
        strokeWidth="1.6"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function Sidebar() {
  const pathname = usePathname();
  const [profile, setProfile] = useState('default');
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setProfile(getAlertProfile());
    setMounted(true);
    return onAlertCuesChange(() => setProfile(getAlertProfile()));
  }, []);

  return (
    <aside className="hidden md:flex md:flex-col md:w-72 px-5 py-6 border-r border-white/10 bg-slate-900/70 text-slate-100 backdrop-blur">
      <div className="flex items-center gap-3 pb-5 border-b border-white/10">
        <div className="h-10 w-10 rounded-2xl bg-gradient-to-br from-amber-500 via-orange-500 to-rose-500 text-white flex items-center justify-center text-lg font-semibold shadow-lg">
          PN
        </div>
        <div>
          <div className="text-xl font-semibold font-display tracking-tight">PDS Netra</div>
          <div className="text-xs text-slate-400">State Command Center</div>
        </div>
      </div>
      <nav className="mt-6 space-y-1">
        {nav.map((item) => {
          const active = pathname === item.href || pathname.startsWith(item.href + '/');
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`group flex items-center justify-between rounded-xl px-3 py-2.5 text-sm transition ${
                active
                  ? 'bg-white/10 shadow-sm border border-white/15 font-semibold text-white'
                  : 'text-slate-300 hover:bg-white/5'
              }`}
            >
              <span className="flex items-center gap-3">
                <item.icon active={active} />
                {item.label}
              </span>
              <span
                className={`h-2 w-2 rounded-full ${
                  active ? 'bg-gradient-to-r from-amber-400 to-rose-500' : 'bg-slate-600 group-hover:bg-amber-200'
                }`}
              />
            </Link>
          );
        })}
      </nav>
      <div className="mt-auto pt-5 text-xs text-slate-400 border-t border-white/10">
        PoC build • GSCSCL
        <div className="mt-2 text-[11px] text-slate-500">AI-powered vigilance for 250+ godowns</div>
        {mounted && (
          <div className="mt-3 inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/5 px-3 py-1 text-[10px] uppercase tracking-[0.3em] text-slate-300">
            Profile: {profile}
          </div>
        )}
      </div>
    </aside>
  );
}
