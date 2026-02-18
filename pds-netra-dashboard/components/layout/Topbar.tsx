'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Select } from '../ui/select';
import { Label } from '../ui/label';
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '../ui/sheet';
import { clearSession, getUser } from '@/lib/auth';
import { logout } from '@/lib/api';
import type { LoginResponse } from '@/lib/types';
import { getAlertCues, getAlertProfile, onAlertCuesChange, setAlertCues, setAlertProfile } from '@/lib/alertCues';
import { getUiPrefs, onUiPrefsChange, setUiPrefs } from '@/lib/uiPrefs';
import { dashboardNav } from './Sidebar';

export function Topbar() {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<LoginResponse['user'] | null>(null);
  const [cues, setCues] = useState(() => getAlertCues());
  const [alertPulse, setAlertPulse] = useState(false);
  const [uiPrefs, setUiPrefsState] = useState(() => getUiPrefs());
  const [showSettings, setShowSettings] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [menuQuery, setMenuQuery] = useState('');
  const [profile, setProfile] = useState(() => getAlertProfile());
  const panelRef = useRef<HTMLDivElement | null>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setUser(getUser());
    setMounted(true);
  }, []);

  useEffect(() => {
    setCues(getAlertCues());
    return onAlertCuesChange(setCues);
  }, []);

  useEffect(() => {
    setUiPrefsState(getUiPrefs());
    return onUiPrefsChange(setUiPrefsState);
  }, []);

  useEffect(() => {
    if (!showSettings) return;
    const onClick = (event: MouseEvent) => {
      const target = event.target as Node | null;
      if (panelRef.current && target && !panelRef.current.contains(target)) {
        setShowSettings(false);
      }
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setShowSettings(false);
    };
    window.addEventListener('mousedown', onClick);
    window.addEventListener('keydown', onKey);
    return () => {
      window.removeEventListener('mousedown', onClick);
      window.removeEventListener('keydown', onKey);
    };
  }, [showSettings]);

  useEffect(() => {
    const handler = (event: Event) => {
      const detail = (event as CustomEvent<{ severity?: string }>).detail;
      if (!cues.visual) return;
      if (detail?.severity) {
        setAlertPulse(true);
        setTimeout(() => setAlertPulse(false), 2200);
      }
    };
    window.addEventListener('pdsnetra-alert-new', handler);
    return () => window.removeEventListener('pdsnetra-alert-new', handler);
  }, [cues.visual]);

  useEffect(() => {
    setMobileMenuOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (!mobileMenuOpen) {
      setMenuQuery('');
    }
  }, [mobileMenuOpen]);

  const toggleVisual = () => {
    setAlertCues({ ...cues, visual: !cues.visual });
  };

  const toggleSound = () => {
    setAlertCues({ ...cues, sound: !cues.sound });
  };

  const toggleRail = () => {
    setUiPrefs({ railOpen: !uiPrefs.railOpen });
  };

  const toggleQuiet = () => {
    setAlertCues({ ...cues, quietHoursEnabled: !cues.quietHoursEnabled });
  };

  const updateThreshold = (value: 'info' | 'warning' | 'critical') => {
    setAlertCues({ ...cues, minSeverity: value });
  };

  const updateQuietStart = (value: string) => {
    setAlertCues({ ...cues, quietHoursStart: value });
  };

  const updateQuietEnd = (value: string) => {
    setAlertCues({ ...cues, quietHoursEnd: value });
  };

  const isQuietNow = (start: string, end: string) => {
    const now = new Date();
    const [sh, sm] = start.split(':').map(Number);
    const [eh, em] = end.split(':').map(Number);
    const startMin = sh * 60 + sm;
    const endMin = eh * 60 + em;
    const nowMin = now.getHours() * 60 + now.getMinutes();
    if (startMin === endMin) return false;
    if (startMin < endMin) return nowMin >= startMin && nowMin < endMin;
    return nowMin >= startMin || nowMin < endMin;
  };

  const quietActive = mounted && cues.quietHoursEnabled && isQuietNow(cues.quietHoursStart, cues.quietHoursEnd);

  const playBeep = (severity: 'info' | 'warning' | 'critical') => {
    try {
      const AudioContext = (window as any).AudioContext || (window as any).webkitAudioContext;
      if (!AudioContext) return;
      const ctx = new AudioContext();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sine';
      osc.frequency.value = severity === 'critical' ? 640 : severity === 'warning' ? 520 : 420;
      gain.gain.value = 0.05;
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.18);
      setTimeout(() => ctx.close(), 250);
    } catch {
      // ignore
    }
  };

  const handleTestAlert = () => {
    const sev = cues.minSeverity;
    if (cues.visual) {
      window.dispatchEvent(new CustomEvent('pdsnetra-alert-new', { detail: { severity: sev } }));
    }
    if (cues.sound && !quietActive) {
      playBeep(sev);
    }
  };

  const handleLogout = async () => {
    try {
      await logout();
    } catch {
      // ignore
    }
    clearSession();
    router.replace('/dashboard/login');
  };

  const handleProfileChange = (value: string) => {
    setProfile(value);
    setAlertProfile(value);
  };

  const filteredNav = useMemo(() => {
    const query = menuQuery.trim().toLowerCase();
    if (!query) return dashboardNav;
    return dashboardNav.filter((item) => {
      return item.label.toLowerCase().includes(query) || item.href.toLowerCase().includes(query);
    });
  }, [menuQuery]);

  return (
    <header className="sticky top-0 z-20 w-full max-w-full border-b border-white/10 bg-slate-900/70 text-slate-100 backdrop-blur relative">
      <div className="flex w-full max-w-full min-w-0 flex-col gap-3 px-4 py-2 md:px-6 md:py-3 lg:px-8">
        <div className="flex w-full max-w-full min-w-0 items-center justify-between gap-2 md:hidden">
          <Button
            variant="ghost"
            size="icon"
            className="rounded-full border border-white/15 bg-white/5 text-slate-100"
            onClick={() => setMobileMenuOpen(true)}
            aria-label="Open navigation menu"
          >
            <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" aria-hidden>
              <path d="M3 5.5H17" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
              <path d="M3 10H17" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
              <path d="M3 14.5H17" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
            </svg>
          </Button>
          <div className="min-w-0 flex-1 truncate text-center text-sm font-semibold tracking-tight">
            PDS Netra
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <Button
              variant="ghost"
              size="icon"
              className="rounded-full border border-white/15 bg-white/5 text-slate-100"
              onClick={() => setShowSettings((prev) => !prev)}
              aria-label="Open settings"
            >
              <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" aria-hidden>
                <path
                  d="M12 8.5a3.5 3.5 0 1 0 0 7a3.5 3.5 0 0 0 0-7Z"
                  stroke="currentColor"
                  strokeWidth="1.6"
                />
                <path
                  d="M19.4 15a1 1 0 0 0 .2 1.1l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1 1 0 0 0-1.1-.2a1 1 0 0 0-.6.9V20a2 2 0 1 1-4 0v-.2a1 1 0 0 0-.6-.9a1 1 0 0 0-1.1.2l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1 1 0 0 0 .2-1.1a1 1 0 0 0-.9-.6H4a2 2 0 1 1 0-4h.2a1 1 0 0 0 .9-.6a1 1 0 0 0-.2-1.1l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1 1 0 0 0 1.1.2a1 1 0 0 0 .6-.9V4a2 2 0 1 1 4 0v.2a1 1 0 0 0 .6.9a1 1 0 0 0 1.1-.2l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1 1 0 0 0-.2 1.1a1 1 0 0 0 .9.6H20a2 2 0 1 1 0 4h-.2a1 1 0 0 0-.9.6Z"
                  stroke="currentColor"
                  strokeWidth="1.4"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="rounded-full border border-white/15 bg-white/5 text-slate-100"
              onClick={handleLogout}
              aria-label="Logout"
            >
              <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" aria-hidden>
                <path
                  d="M15 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h8"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                />
                <path
                  d="M10 12H21M21 12l-3-3M21 12l-3 3"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </Button>
          </div>
        </div>

        <div className="hidden w-full max-w-full min-w-0 flex-col gap-3 md:flex md:flex-row md:items-start md:justify-between">
          <div className="min-w-0">
            <div className="text-[11px] uppercase tracking-[0.2em] text-slate-400 sm:text-sm">Control Deck</div>
            <div className="truncate text-lg font-semibold font-display tracking-tight sm:text-xl">
              PDS Netra Dashboard
            </div>
            <div className="mt-1 inline-flex items-center gap-2 text-[10px] uppercase tracking-[0.25em] text-slate-400 sm:text-[11px] sm:tracking-[0.3em]">
              <span className="h-1.5 w-1.5 rounded-full bg-amber-400" />
              Live perimeter
            </div>
            {quietActive && (
              <div className="mt-2 inline-flex items-center gap-2 text-[10px] uppercase tracking-[0.25em] text-slate-500 sm:tracking-[0.3em]">
                <span className="h-1.5 w-1.5 rounded-full bg-slate-400" />
                Quiet hours active
              </div>
            )}
          </div>
          <div className="flex w-full max-w-full min-w-0 flex-wrap items-center gap-2 sm:w-auto sm:justify-end sm:gap-3">
            <div className="hidden lg:flex min-w-0 items-center gap-2">
              <Button
                variant="ghost"
                className={`rounded-full px-3 py-1 text-[11px] uppercase tracking-[0.2em] ${cues.visual ? 'btn-outline' : 'opacity-60'}`}
                onClick={toggleVisual}
              >
                Visual
              </Button>
              <Button
                variant="ghost"
                className={`rounded-full px-3 py-1 text-[11px] uppercase tracking-[0.2em] ${cues.sound ? 'btn-outline' : 'opacity-60'}`}
                onClick={toggleSound}
              >
                Sound
              </Button>
              <Button
                variant="ghost"
                className={`rounded-full px-3 py-1 text-[11px] uppercase tracking-[0.2em] ${cues.quietHoursEnabled ? 'btn-outline' : 'opacity-60'}`}
                onClick={toggleQuiet}
              >
                Quiet
              </Button>
              <Button
                variant="ghost"
                className={`rounded-full px-3 py-1 text-[11px] uppercase tracking-[0.2em] ${uiPrefs.railOpen ? 'btn-outline' : 'opacity-60'}`}
                onClick={toggleRail}
              >
                Rail
              </Button>
              <span className={`pulse-dot ${alertPulse ? 'pulse-warning' : 'pulse-info'}`} />
            </div>
            <Button
              variant="ghost"
              className="rounded-full px-2.5 py-1 text-[10px] uppercase tracking-[0.2em] btn-outline sm:px-3 sm:text-[11px]"
              onClick={() => setShowSettings((prev) => !prev)}
            >
              Settings
            </Button>
            {user ? (
              <>
                <div className="hidden md:block min-w-0 truncate text-sm text-slate-200">
                  {user.name ?? user.username}
                </div>
                {mounted && <Badge variant="outline" className="hidden md:inline-flex min-w-0">Profile: {profile}</Badge>}
                <Badge variant="outline" className="hidden sm:inline-flex min-w-0">{user.role}</Badge>
                <Button
                  variant="outline"
                  className="text-xs sm:text-sm"
                  onClick={handleLogout}
                >
                  Logout
                </Button>
              </>
            ) : (
              <Badge variant="outline" className="text-[11px]">Not signed in</Badge>
            )}
          </div>
        </div>
      </div>
      {mounted && showSettings && (
        <div ref={panelRef} className="settings-panel animate-fade-up">
          <div className="flex items-center justify-between mb-3">
            <div>
              <div className="text-xs uppercase tracking-[0.3em] text-slate-400">Alert Settings</div>
              <div className="text-base font-semibold text-white">
                {user?.name ?? user?.username ?? 'Default profile'}
              </div>
            </div>
            <button
              className="text-xs uppercase tracking-[0.3em] text-slate-400"
              onClick={() => setShowSettings(false)}
            >
              Close
            </button>
          </div>

          <div className="grid grid-cols-1 gap-3">
            <div>
              <Label>Alert profile</Label>
              <Select
                value={profile}
                onChange={(e) => handleProfileChange(e.target.value)}
                options={[
                  { label: 'Default', value: 'default' },
                  { label: 'Shift A', value: 'shift-a' },
                  { label: 'Shift B', value: 'shift-b' },
                  { label: 'Night Ops', value: 'night-ops' }
                ]}
              />
            </div>
            <div>
              <Label>Minimum severity</Label>
              <Select
                value={cues.minSeverity}
                onChange={(e) => updateThreshold(e.target.value as 'info' | 'warning' | 'critical')}
                options={[
                  { label: 'Info', value: 'info' },
                  { label: 'Warning', value: 'warning' },
                  { label: 'Critical', value: 'critical' }
                ]}
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>Quiet start</Label>
                <Input type="time" value={cues.quietHoursStart} onChange={(e) => updateQuietStart(e.target.value)} />
              </div>
              <div>
                <Label>Quiet end</Label>
                <Input type="time" value={cues.quietHoursEnd} onChange={(e) => updateQuietEnd(e.target.value)} />
              </div>
            </div>

            <div className="flex items-center justify-between text-xs uppercase tracking-[0.3em] text-slate-400">
              <span>Quiet hours</span>
              <span>{cues.quietHoursEnabled ? 'Enabled' : 'Disabled'}</span>
            </div>

            <Button className="w-full" onClick={handleTestAlert}>
              Test alert
            </Button>
          </div>
        </div>
      )}
      <Sheet open={mobileMenuOpen} onOpenChange={setMobileMenuOpen}>
        <SheetContent side="left" className="w-[92vw] max-w-[360px] overflow-y-auto border-r border-white/15 bg-slate-950/98">
          <SheetHeader className="space-y-2 bg-gradient-to-r from-slate-950 to-slate-900/80">
            <div className="flex items-center justify-between gap-2">
              <div className="inline-flex w-fit items-center gap-2 rounded-full border border-white/15 bg-white/5 px-3 py-1.5 text-[10px] uppercase tracking-[0.28em] text-slate-300">
                PDS Netra
              </div>
              <button
                type="button"
                className="rounded-full border border-white/10 bg-white/5 p-2 text-slate-300 hover:text-white"
                onClick={() => setMobileMenuOpen(false)}
                aria-label="Close navigation"
              >
                <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" aria-hidden>
                  <path d="M5 5L15 15" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
                  <path d="M15 5L5 15" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
                </svg>
              </button>
            </div>
            <SheetTitle>Navigation</SheetTitle>
            <SheetDescription>Switch modules quickly on mobile</SheetDescription>
            {user ? (
              <div className="flex items-center gap-2 pt-1 text-xs text-slate-300">
                <span className="truncate">{user.name ?? user.username}</span>
                <span className="rounded-full border border-white/15 bg-white/5 px-2 py-0.5 text-[10px] uppercase tracking-[0.2em] text-slate-300">
                  {user.role}
                </span>
              </div>
            ) : null}
          </SheetHeader>
          <div className="p-3">
            <Input
              value={menuQuery}
              onChange={(e) => setMenuQuery(e.target.value)}
              placeholder="Search module..."
              className="h-10 rounded-lg border-white/20 bg-white/5 text-slate-100 placeholder:text-slate-500 shadow-none"
            />
          </div>
          <nav className="space-y-1 p-3 pt-0">
            {filteredNav.map((item) => {
              const active = pathname === item.href || pathname.startsWith(item.href + '/');
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setMobileMenuOpen(false)}
                  className={`group flex items-center justify-between rounded-xl px-3 py-2.5 text-sm transition ${
                    active
                      ? 'border border-white/20 bg-white/10 text-white shadow-sm'
                      : 'text-slate-300 hover:bg-white/5'
                  }`}
                >
                  <span className="flex min-w-0 items-center gap-3">
                    <item.icon active={active} />
                    <span className="truncate">{item.label}</span>
                  </span>
                  <span
                    className={`h-2 w-2 rounded-full ${
                      active ? 'bg-gradient-to-r from-amber-400 to-rose-500' : 'bg-slate-600 group-hover:bg-slate-400'
                    }`}
                  />
                </Link>
              );
            })}
            {filteredNav.length === 0 ? (
              <div className="rounded-xl border border-white/10 bg-white/5 px-3 py-4 text-center text-xs uppercase tracking-[0.2em] text-slate-400">
                No matching module
              </div>
            ) : null}
          </nav>
          <div className="p-3 pb-6">
            <div className="grid grid-cols-2 gap-2">
              <Button
                variant="ghost"
                className="rounded-xl border border-white/15 bg-white/5 text-xs uppercase tracking-[0.2em] text-slate-200 hover:bg-white/10"
                onClick={() => {
                  setMobileMenuOpen(false);
                  setShowSettings(true);
                }}
              >
                Settings
              </Button>
              <Button
                variant="outline"
                className="rounded-xl text-xs uppercase tracking-[0.2em]"
                onClick={() => {
                  setMobileMenuOpen(false);
                  handleLogout();
                }}
              >
                Logout
              </Button>
            </div>
          </div>
        </SheetContent>
      </Sheet>
    </header>
  );
}
