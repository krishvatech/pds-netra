'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';
import { getAlertProfile, onAlertCuesChange } from '@/lib/alertCues';
import type { LoginResponse } from '@/lib/types';

export const dashboardNav = [
  { href: '/dashboard/command-center', label: 'Command Center', icon: CommandIcon },
  { href: '/dashboard/overview', label: 'Overview', icon: OverviewIcon },
  { href: '/dashboard/godowns', label: 'Godowns', icon: WarehouseIcon },
  { href: '/dashboard/cameras', label: 'Cameras', icon: CameraIcon },
  { href: '/dashboard/authorized-users', label: 'Authorized Users', icon: UsersIcon },
  { href: '/dashboard/alerts', label: 'Alerts', icon: AlertIcon },
  { href: '/dashboard/after-hours', label: 'After-hours', icon: AfterHoursIcon },
  { href: '/dashboard/after-hours/policies', label: 'After-hours Policies', icon: AfterHoursPolicyIcon },
  { href: '/dashboard/watchlist', label: 'Watchlist', icon: WatchlistIcon },
  { href: '/dashboard/animals', label: 'Animals', icon: AnimalsIcon },
  { href: '/dashboard/fire', label: 'Fire', icon: FireIcon },
  { href: '/dashboard/incidents', label: 'Incidents', icon: IncidentIcon },
  { href: '/dashboard/reports', label: 'Reports', icon: ReportIcon },
  { href: '/dashboard/health', label: 'Health', icon: HeartbeatIcon },
  { href: '/dashboard/rules', label: 'Rules', icon: RulesIcon },
  { href: '/dashboard/notifications', label: 'Notifications', icon: NotificationIcon },
  { href: '/dashboard/dispatch-movement', label: 'Dispatch Movement', icon: DispatchMovementIcon },
  { href: '/dashboard/dispatch', label: 'Dispatch', icon: DispatchIcon },
  { href: '/dashboard/live', label: 'Live Cameras', icon: LiveIcon },
  { href: '/dashboard/anpr', label: 'ANPR', icon: PlateIcon },
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

function CommandIcon({ active }: { active: boolean }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M4 7H20M4 12H20M4 17H20"
        stroke={active ? '#f59e0b' : '#64748b'}
        strokeWidth="1.8"
        strokeLinecap="round"
      />
      <circle cx="8" cy="7" r="1.5" fill={active ? '#f59e0b' : '#64748b'} />
      <circle cx="14" cy="12" r="1.5" fill={active ? '#f59e0b' : '#64748b'} />
      <circle cx="10" cy="17" r="1.5" fill={active ? '#f59e0b' : '#64748b'} />
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

function CameraIcon({ active }: { active: boolean }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
      <rect
        x="3"
        y="7"
        width="12"
        height="10"
        rx="2"
        stroke={active ? '#f59e0b' : '#64748b'}
        strokeWidth="1.6"
      />
      <path
        d="M15 9L21 7V17L15 15"
        stroke={active ? '#f59e0b' : '#64748b'}
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <circle
        cx="9"
        cy="12"
        r="2"
        stroke={active ? '#f59e0b' : '#64748b'}
        strokeWidth="1.6"
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

function WatchlistIcon({ active }: { active: boolean }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
      <circle
        cx="11"
        cy="8"
        r="3.5"
        stroke={active ? '#f59e0b' : '#64748b'}
        strokeWidth="1.6"
      />
      <path
        d="M4 20C4.5 16.5 7.2 14 11 14C14.8 14 17.5 16.5 18 20"
        stroke={active ? '#f59e0b' : '#64748b'}
        strokeWidth="1.6"
        strokeLinecap="round"
      />
      <path
        d="M16 6L19 9L22 4"
        stroke={active ? '#f59e0b' : '#64748b'}
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function AnimalsIcon({ active }: { active: boolean }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
      <circle cx="7.5" cy="7" r="2" fill={active ? '#f59e0b' : '#64748b'} />
      <circle cx="12" cy="6" r="2" fill={active ? '#f59e0b' : '#64748b'} />
      <circle cx="16.5" cy="7" r="2" fill={active ? '#f59e0b' : '#64748b'} />
      <path
        d="M6 16.5C6 14 8.2 12 12 12C15.8 12 18 14 18 16.5C18 19 15.8 21 12 21C8.2 21 6 19 6 16.5Z"
        stroke={active ? '#f59e0b' : '#64748b'}
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function FireIcon({ active }: { active: boolean }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M12 3C9 6 8 8 8 10.5C8 13.5 10.2 15.5 12 18C14 15.5 16 14 16 10.5C16 8 14.8 6 12 3Z"
        stroke={active ? '#f59e0b' : '#64748b'}
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <path
        d="M12 21C9.8 20.2 8.5 18.6 8.5 16.6C8.5 14.6 10 13 12 12"
        stroke={active ? '#f59e0b' : '#64748b'}
        strokeWidth="1.6"
        strokeLinecap="round"
      />
    </svg>
  );
}

function AfterHoursIcon({ active }: { active: boolean }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M12 7V12L15 14"
        stroke={active ? '#f59e0b' : '#64748b'}
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle
        cx="12"
        cy="12"
        r="8"
        stroke={active ? '#f59e0b' : '#64748b'}
        strokeWidth="1.6"
      />
      <path
        d="M4 4L7 7"
        stroke={active ? '#f59e0b' : '#64748b'}
        strokeWidth="1.6"
        strokeLinecap="round"
      />
    </svg>
  );
}

function AfterHoursPolicyIcon({ active }: { active: boolean }) {
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
        strokeLinecap="round"
      />
      <path
        d="M8 13H16M8 17H14"
        stroke={active ? '#f59e0b' : '#64748b'}
        strokeWidth="1.6"
        strokeLinecap="round"
      />
    </svg>
  );
}

function IncidentIcon({ active }: { active: boolean }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M12 3L21 19H3L12 3Z"
        stroke={active ? '#f59e0b' : '#64748b'}
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <path
        d="M12 9V13"
        stroke={active ? '#f59e0b' : '#64748b'}
        strokeWidth="1.8"
        strokeLinecap="round"
      />
      <circle cx="12" cy="16.5" r="1.1" fill={active ? '#f59e0b' : '#64748b'} />
    </svg>
  );
}

function ReportIcon({ active }: { active: boolean }) {
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
        d="M8 12H16"
        stroke={active ? '#f59e0b' : '#64748b'}
        strokeWidth="1.6"
        strokeLinecap="round"
      />
      <path
        d="M8 16H14"
        stroke={active ? '#f59e0b' : '#64748b'}
        strokeWidth="1.6"
        strokeLinecap="round"
      />
    </svg>
  );
}

function DispatchMovementIcon({ active }: { active: boolean }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M4 12H20"
        stroke={active ? '#f59e0b' : '#64748b'}
        strokeWidth="1.8"
        strokeLinecap="round"
      />
      <path
        d="M14 6L20 12L14 18"
        stroke={active ? '#f59e0b' : '#64748b'}
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <rect
        x="3"
        y="5"
        width="6"
        height="14"
        rx="2"
        stroke={active ? '#f59e0b' : '#64748b'}
        strokeWidth="1.6"
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

function DispatchIcon({ active }: { active: boolean }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M3 6H15V16H3V6Z"
        stroke={active ? '#f59e0b' : '#64748b'}
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <path
        d="M15 9H19L21 12V16H15V9Z"
        stroke={active ? '#f59e0b' : '#64748b'}
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <circle cx="7" cy="18" r="1.6" fill={active ? '#f59e0b' : '#64748b'} />
      <circle cx="17" cy="18" r="1.6" fill={active ? '#f59e0b' : '#64748b'} />
    </svg>
  );
}

function RulesIcon({ active }: { active: boolean }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M5 4H19V8H5V4Z"
        stroke={active ? '#f59e0b' : '#64748b'}
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <path
        d="M5 10H19V14H5V10Z"
        stroke={active ? '#f59e0b' : '#64748b'}
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <path
        d="M5 16H19V20H5V16Z"
        stroke={active ? '#f59e0b' : '#64748b'}
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function NotificationIcon({ active }: { active: boolean }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
      <rect
        x="4"
        y="5"
        width="16"
        height="12"
        rx="2"
        stroke={active ? '#f59e0b' : '#64748b'}
        strokeWidth="1.6"
      />
      <path
        d="M6 8L12 12L18 8"
        stroke={active ? '#f59e0b' : '#64748b'}
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="18.5" cy="17.5" r="2" fill={active ? '#f59e0b' : '#64748b'} />
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

// Resolved: Added UsersIcon from upstream
function UsersIcon({ active }: { active: boolean }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
      <circle
        cx="9"
        cy="7"
        r="3"
        stroke={active ? '#f59e0b' : '#64748b'}
        strokeWidth="1.6"
      />
      <path
        d="M3 18C3 15.2386 5.23858 13 8 13H10C12.7614 13 15 15.2386 15 18"
        stroke={active ? '#f59e0b' : '#64748b'}
        strokeWidth="1.6"
        strokeLinecap="round"
      />
      <circle
        cx="17"
        cy="7"
        r="2"
        stroke={active ? '#f59e0b' : '#64748b'}
        strokeWidth="1.6"
      />
      <path
        d="M18 13C19.6569 13 21 14.3431 21 16V18"
        stroke={active ? '#f59e0b' : '#64748b'}
        strokeWidth="1.6"
        strokeLinecap="round"
      />
    </svg>
  );
}

// Resolved: Added PlateIcon from stashed changes
function PlateIcon({ active }: { active: boolean }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
      <rect
        x="3"
        y="7"
        width="18"
        height="10"
        rx="2"
        stroke={active ? '#f59e0b' : '#64748b'}
        strokeWidth="1.8"
      />
      <path
        d="M7 10.5H17M7 13.5H15"
        stroke={active ? '#f59e0b' : '#64748b'}
        strokeWidth="1.6"
        strokeLinecap="round"
      />
    </svg>
  );
}

const GODOWN_NAV_EXCLUDE = new Set(['/dashboard/command-center', '/dashboard/overview']);

function filterNavByRole(user: LoginResponse['user'] | null) {
  if (!user) return dashboardNav;
  if (user.role === 'GODOWN_MANAGER') {
    return dashboardNav.filter((item) => !GODOWN_NAV_EXCLUDE.has(item.href));
  }
  return dashboardNav;
}

export function Sidebar({ user }: { user: LoginResponse['user'] | null }) {
  const pathname = usePathname();
  const [profile, setProfile] = useState('default');
  const [mounted, setMounted] = useState(false);
  const navItems = filterNavByRole(user);

  useEffect(() => {
    setProfile(getAlertProfile());
    setMounted(true);
    return onAlertCuesChange(() => setProfile(getAlertProfile()));
  }, []);

  return (
    <aside className="hidden md:flex md:flex-col md:w-[260px] md:shrink-0 md:h-full md:overflow-y-auto px-4 lg:px-5 py-6 border-r border-white/10 bg-slate-900/70 text-slate-100 backdrop-blur">
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
        {navItems.map((item) => {
          const active = pathname === item.href || pathname.startsWith(item.href + '/');
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`group flex items-center justify-between rounded-xl px-3 py-2.5 text-sm transition ${active
                  ? 'bg-white/10 shadow-sm border border-white/15 font-semibold text-white'
                  : 'text-slate-300 hover:bg-white/5'
                }`}
            >
              <span className="flex items-center gap-3">
                <item.icon active={active} />
                {item.label}
              </span>
              <span
                className={`h-2 w-2 rounded-full ${active ? 'bg-gradient-to-r from-amber-400 to-rose-500' : 'bg-slate-600 group-hover:bg-amber-200'
                  }`}
              />
            </Link>
          );
        })}
      </nav>
      <div className="mt-auto pt-5 text-xs text-slate-400 border-t border-white/10">
        <div className="flex flex-wrap items-center gap-2">
          <span>PoC build</span>
          <span className="text-slate-500">•</span>
          <span>GSCSCL</span>
        </div>
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
