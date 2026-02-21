'use client';
'use client';

import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { LogOut, Menu, Settings } from 'lucide-react';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Select } from '../ui/select';
import { Label } from '../ui/label';
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '../ui/sheet';
import { clearSession, getUser } from '@/lib/auth';
import { logout } from '@/lib/api';
import type { LoginResponse } from '@/lib/types';
import {
  DEFAULT_ALERT_CUES,
  getAlertCues,
  getAlertProfile,
  onAlertCuesChange,
  setAlertCues,
  setAlertProfile,
  syncAlertCuesCookie
} from '@/lib/alertCues';
import { DEFAULT_UI_PREFS, getUiPrefs, onUiPrefsChange, setUiPrefs, syncUiPrefsCookie } from '@/lib/uiPrefs';
import { dashboardNav } from './Sidebar';

export function Topbar({
  user: userProp,
  initialAlertCues,
  initialUiPrefs
}: {
  user?: LoginResponse['user'] | null;
  initialAlertCues?: ReturnType<typeof getAlertCues> | null;
  initialUiPrefs?: ReturnType<typeof getUiPrefs> | null;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const iconBtn =
    'h-11 w-11 rounded-full border border-white/15 bg-white/5 text-white/90 shadow-[inset_0_1px_0_rgba(255,255,255,0.18),0_6px_16px_rgba(0,0,0,0.25)] hover:bg-white/10 active:bg-white/15 inline-flex items-center justify-center transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/20';
  const iconSize = 'h-6 w-6';
  const menuIconSize = 'h-5 w-7';
  const [user, setUser] = useState<LoginResponse['user'] | null>(userProp ?? null);
  const [cues, setCues] = useState(() => initialAlertCues ?? DEFAULT_ALERT_CUES);
  const [alertPulse, setAlertPulse] = useState(false);
  const [uiPrefs, setUiPrefsState] = useState(() => initialUiPrefs ?? DEFAULT_UI_PREFS);
  const [showSettings, setShowSettings] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [menuQuery, setMenuQuery] = useState('');
  const [profile, setProfile] = useState(() => getAlertProfile());
  const [controlsExpanded, setControlsExpanded] = useState(false);
  const panelRef = useRef<HTMLDivElement | null>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    if (userProp !== undefined) {
      setUser(userProp);
      setMounted(true);
      return;
    }
    setUser(getUser());
    setMounted(true);
  }, [userProp]);

  useLayoutEffect(() => {
    if (initialAlertCues == null) {
      setCues(getAlertCues());
      syncAlertCuesCookie();
    }
    if (initialUiPrefs == null) {
      setUiPrefsState(getUiPrefs());
      syncUiPrefsCookie();
    }
  }, [initialAlertCues, initialUiPrefs]);

  useEffect(() => {
    if (initialAlertCues == null) {
      setCues(getAlertCues());
    }
    return onAlertCuesChange(setCues);
  }, [initialAlertCues]);

  useEffect(() => {
    if (initialUiPrefs == null) {
      setUiPrefsState(getUiPrefs());
    }
    return onUiPrefsChange(setUiPrefsState);
  }, [initialUiPrefs]);

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
      setControlsExpanded(false);
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

  const renderControlDeckPanel = (layout: 'compact' | 'full') => {
    const isCompact = layout === 'compact';
    return (
      <div className={`space-y-3 ${isCompact ? '' : 'px-4 pb-6 pt-4'}`}>
        <div className={`${isCompact ? '' : 'rounded-2xl border border-white/10 bg-white/5 p-3'}`}>
          <div className="text-[11px] uppercase tracking-[0.28em] text-slate-400">Mode</div>
          <div className="mt-2 flex w-full rounded-xl bg-slate-900/70 p-1">
            <button
              type="button"
              className={`h-11 flex-1 rounded-lg text-xs uppercase tracking-[0.22em] transition ${cues.visual ? 'bg-white/10 text-white' : 'text-slate-400'}`}
              onClick={toggleVisual}
              aria-pressed={cues.visual}
            >
              Visual
            </button>
            <button
              type="button"
              className={`h-11 flex-1 rounded-lg text-xs uppercase tracking-[0.22em] transition ${cues.sound ? 'bg-white/10 text-white' : 'text-slate-400'}`}
              onClick={toggleSound}
              aria-pressed={cues.sound}
            >
              Sound
            </button>
          </div>
          <div className="mt-2 flex items-center justify-between text-[10px] uppercase tracking-[0.24em] text-slate-500">
            <span>Alert pulse</span>
            <span className={`pulse-dot ${alertPulse ? 'pulse-warning' : 'pulse-info'}`} />
          </div>
        </div>

        <div className="space-y-2">
          <div className="flex items-center justify-between rounded-lg border border-white/10 bg-white/5 px-3 py-2">
            <div>
              <div className="text-sm font-semibold text-white">Quiet</div>
              <div className="text-[10px] uppercase tracking-[0.22em] text-slate-500">Quiet hours</div>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={cues.quietHoursEnabled}
              className={`relative inline-flex h-6 w-11 items-center rounded-full border border-white/10 transition ${cues.quietHoursEnabled ? 'bg-emerald-500/60' : 'bg-white/10'}`}
              onClick={toggleQuiet}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white transition ${cues.quietHoursEnabled ? 'translate-x-5' : 'translate-x-1'}`}
              />
            </button>
          </div>
          <div className="flex items-center justify-between rounded-lg border border-white/10 bg-white/5 px-3 py-2">
            <div>
              <div className="text-sm font-semibold text-white">Rail</div>
              <div className="text-[10px] uppercase tracking-[0.22em] text-slate-500">Live feed panel</div>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={uiPrefs.railOpen}
              className={`relative inline-flex h-6 w-11 items-center rounded-full border border-white/10 transition ${uiPrefs.railOpen ? 'bg-amber-400/70' : 'bg-white/10'}`}
              onClick={toggleRail}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white transition ${uiPrefs.railOpen ? 'translate-x-5' : 'translate-x-1'}`}
              />
            </button>
          </div>
        </div>

        <Button
          variant="ghost"
          className="h-11 w-full rounded-xl text-xs uppercase tracking-[0.24em] btn-outline"
          onClick={() => {
            setMobileMenuOpen(false);
            setShowSettings(true);
          }}
        >
          Settings
        </Button>
      </div>
    );
  };

  const filteredNav = useMemo(() => {
    const query = menuQuery.trim().toLowerCase();
    if (!query) return dashboardNav;
    return dashboardNav.filter((item) => {
      return item.label.toLowerCase().includes(query) || item.href.toLowerCase().includes(query);
    });
  }, [menuQuery]);

  return (
    <header className="relative z-20 border-b border-white/10 bg-slate-900/70 px-4 py-3 text-slate-100 backdrop-blur">
      <div className="flex w-full min-w-0 flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0 w-full lg:w-auto">
          <div className="relative mb-1 flex items-center gap-2 lg:hidden">
            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                size="icon"
                className={iconBtn}
                onClick={() => setMobileMenuOpen(true)}
                aria-label="Open navigation menu"
              >
                <Menu className={menuIconSize} strokeWidth={2.6} aria-hidden />
              </Button>
            </div>
            <div className="pointer-events-none absolute left-1/2 max-w-[60%] -translate-x-1/2 truncate text-center text-base font-semibold font-display tracking-tight">
              PDS Netra
            </div>
            <div className="ml-auto flex items-center gap-2">
              <Button
                variant="ghost"
                size="icon"
                className={iconBtn}
                onClick={() => setShowSettings((prev) => !prev)}
                aria-label="Open settings"
                title="Open settings"
              >
                <Settings className={iconSize} aria-hidden />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className={iconBtn}
                onClick={handleLogout}
                aria-label="Logout"
                title="Logout"
              >
                <LogOut className={iconSize} aria-hidden />
              </Button>
            </div>
          </div>
          <div className="hidden text-[11px] uppercase tracking-[0.2em] text-slate-400 lg:block sm:text-sm">Control Deck</div>
          <div className="hidden truncate text-lg font-semibold font-display tracking-tight lg:block sm:text-xl">PDS Netra Dashboard</div>
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
        <div className="hidden lg:flex w-full flex-wrap items-center gap-2 sm:w-auto sm:justify-end sm:gap-3">
          <div className="hidden lg:flex items-center gap-2">
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
              <div className="hidden lg:block text-sm text-slate-200">
                {user.name ?? user.username}
              </div>
              {mounted && <Badge variant="outline" className="hidden lg:inline-flex">Profile: {profile}</Badge>}
              <Badge variant="outline" className="hidden sm:inline-flex">{user.role}</Badge>
              <Button
                variant="outline"
                className="inline-flex items-center gap-1.5 rounded-full border border-rose-500/60 bg-rose-500/10 px-3 py-1 text-[11px] uppercase tracking-[0.2em] text-rose-300 shadow-[0_0_8px_rgba(244,63,94,0.25)] transition hover:border-rose-400 hover:bg-rose-500/20 hover:text-rose-200 hover:shadow-[0_0_14px_rgba(244,63,94,0.4)] active:scale-95 sm:px-4 sm:text-xs"
                onClick={handleLogout}
                aria-label="Logout"
              >
                <LogOut className="h-3.5 w-3.5 shrink-0" aria-hidden />
                Logout
              </Button>
            </>
          ) : (
            <Badge variant="outline" className="text-[11px]">Not signed in</Badge>
          )}
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

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
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
              className="h-10 rounded-lg border border-white/20 bg-white/90 text-slate-900 placeholder:text-slate-500 shadow-none transition"
            />
          </div>
          <nav className="space-y-1 p-3 pt-0">
            <div className="mb-3 rounded-xl border border-white/10 bg-white/5">
              <button
                type="button"
                className="flex w-full items-center justify-between px-3 py-2.5 text-sm text-slate-200"
                onClick={() => setControlsExpanded((prev) => !prev)}
                aria-expanded={controlsExpanded}
              >
                <span className="flex items-center gap-2 text-xs uppercase tracking-[0.2em]">
                  <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" aria-hidden>
                    <path d="M4 7H20" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
                    <path d="M4 12H20" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
                    <path d="M4 17H20" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
                  </svg>
                  Controls
                </span>
                <svg
                  viewBox="0 0 20 20"
                  className={`h-4 w-4 transition ${controlsExpanded ? 'rotate-180' : ''}`}
                  fill="none"
                  aria-hidden
                >
                  <path d="M5 8L10 13L15 8" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
                </svg>
              </button>
              {controlsExpanded && (
                <div className="border-t border-white/10 px-3 py-3">
                  {renderControlDeckPanel('compact')}
                </div>
              )}
            </div>
            {filteredNav.map((item) => {
              const active = pathname === item.href || pathname.startsWith(item.href + '/');
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setMobileMenuOpen(false)}
                  className={`group flex items-center justify-between rounded-xl px-3 py-2.5 text-sm transition ${active
                    ? 'border border-white/20 bg-white/10 text-white shadow-sm'
                    : 'text-slate-300 hover:bg-white/5'
                    }`}
                >
                  <span className="flex min-w-0 items-center gap-3">
                    <item.icon active={active} />
                    <span className="truncate">{item.label}</span>
                  </span>
                  <span
                    className={`h-2 w-2 rounded-full ${active ? 'bg-gradient-to-r from-amber-400 to-rose-500' : 'bg-slate-600 group-hover:bg-slate-400'
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
          <div className="p-3 pb-6" />
        </SheetContent>
      </Sheet>
    </header>
  );
}
