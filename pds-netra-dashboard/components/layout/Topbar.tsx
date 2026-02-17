'use client';

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Select } from '../ui/select';
import { Label } from '../ui/label';
import { clearSession, getUser } from '@/lib/auth';
import { logout } from '@/lib/api';
import type { LoginResponse } from '@/lib/types';
import { getAlertCues, getAlertProfile, onAlertCuesChange, setAlertCues, setAlertProfile } from '@/lib/alertCues';
import { getUiPrefs, onUiPrefsChange, setUiPrefs } from '@/lib/uiPrefs';

export function Topbar() {
  const router = useRouter();
  const [user, setUser] = useState<LoginResponse['user'] | null>(null);
  const [cues, setCues] = useState(() => getAlertCues());
  const [alertPulse, setAlertPulse] = useState(false);
  const [uiPrefs, setUiPrefsState] = useState(() => getUiPrefs());
  const [showSettings, setShowSettings] = useState(false);
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

  const handleProfileChange = (value: string) => {
    setProfile(value);
    setAlertProfile(value);
  };

  return (
    <header className="sticky top-0 z-20 border-b border-white/10 bg-slate-900/70 px-4 py-3 text-slate-100 backdrop-blur relative">
      <div className="flex w-full min-w-0 flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="text-[11px] uppercase tracking-[0.2em] text-slate-400 sm:text-sm">Control Deck</div>
          <div className="truncate text-lg font-semibold font-display tracking-tight sm:text-xl">PDS Netra Dashboard</div>
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
        <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto sm:justify-end sm:gap-3">
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
              <div className="hidden md:block text-sm text-slate-200">
                {user.name ?? user.username}
              </div>
              {mounted && <Badge variant="outline" className="hidden md:inline-flex">Profile: {profile}</Badge>}
              <Badge variant="outline" className="hidden sm:inline-flex">{user.role}</Badge>
              <Button
                variant="outline"
                className="text-xs sm:text-sm"
                onClick={async () => {
                  try {
                    await logout();
                  } catch {
                    // ignore
                  }
                  clearSession();
                  router.replace('/dashboard/login');
                }}
              >
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
    </header>
  );
}
