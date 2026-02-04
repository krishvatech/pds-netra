'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { acknowledgeAlert, getAlerts } from '@/lib/api';
import type { AlertItem, Severity } from '@/lib/types';
import { formatUtc, humanAlertType } from '@/lib/formatters';
import { getAlertCues, onAlertCuesChange } from '@/lib/alertCues';
import { getUiPrefs, onUiPrefsChange, setUiPrefs } from '@/lib/uiPrefs';

const POLL_INTERVAL_MS = 15000;

function severityRank(sev: Severity) {
  if (sev === 'critical') return 3;
  if (sev === 'warning') return 2;
  return 1;
}

function alertPriority(alert: AlertItem): number {
  if (alert.alert_type === 'FIRE_DETECTED') return 5;
  if (alert.alert_type === 'BLACKLIST_PERSON_MATCH') return 4;
  if (alert.alert_type === 'ANPR_PLATE_BLACKLIST') return 4;
  if (alert.alert_type === 'ANPR_PLATE_NOT_VERIFIED') return 3;
  if (alert.alert_type === 'AFTER_HOURS_PERSON_PRESENCE') return 3;
  if (alert.alert_type === 'AFTER_HOURS_VEHICLE_PRESENCE') return 3;
  return 0;
}

function isQuietNow(start: string, end: string) {
  const now = new Date();
  const [sh, sm] = start.split(':').map(Number);
  const [eh, em] = end.split(':').map(Number);
  const startMin = sh * 60 + sm;
  const endMin = eh * 60 + em;
  const nowMin = now.getHours() * 60 + now.getMinutes();
  if (startMin === endMin) return false;
  if (startMin < endMin) return nowMin >= startMin && nowMin < endMin;
  return nowMin >= startMin || nowMin < endMin;
}

function playBeep(sev: Severity) {
  if (typeof window === 'undefined') return;
  try {
    const AudioContext = (window as any).AudioContext || (window as any).webkitAudioContext;
    if (!AudioContext) return;
    const ctx = new AudioContext();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = 'sine';
    osc.frequency.value = sev === 'critical' ? 640 : sev === 'warning' ? 520 : 420;
    gain.gain.value = 0.05;
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.18);
    setTimeout(() => ctx.close(), 250);
  } catch {
    // Ignore audio failures (autoplay restrictions, etc.)
  }
}

function formatAnimalLabel(value?: string | null) {
  if (!value) return null;
  const trimmed = value.trim();
  if (!trimmed) return null;
  return trimmed.charAt(0).toUpperCase() + trimmed.slice(1);
}

function alertTitle(alert: AlertItem): string {
  const base = humanAlertType(alert.alert_type);
  if (alert.alert_type !== 'ANIMAL_INTRUSION') return base;
  const animal = formatAnimalLabel(alert.key_meta?.animal_label ?? alert.key_meta?.animal_species ?? null);
  return animal ? `${base} • ${animal}` : base;
}

function formatScore(raw?: unknown) {
  if (raw === null || raw === undefined) return null;
  const val = typeof raw === 'number' ? raw : Number(raw);
  if (Number.isNaN(val)) return null;
  return val.toFixed(3);
}

function alertDetail(alert: AlertItem): string | null {
  if (alert.alert_type === 'BLACKLIST_PERSON_MATCH') {
    const name = alert.key_meta?.person_name ?? 'Unknown';
    const score = formatScore(alert.key_meta?.match_score);
    return score ? `Blacklisted: ${name} | Match ${score}` : `Blacklisted: ${name}`;
  }
  return null;
}

function alertEpoch(alert: AlertItem): number | null {
  const ts = alert.end_time ?? alert.start_time;
  if (!ts) return null;
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return null;
  return d.getTime();
}

function timeAgo(alert: AlertItem): string {
  const ts = alertEpoch(alert);
  if (!ts) return '-';
  const diffSec = Math.max(0, Math.floor((Date.now() - ts) / 1000));
  if (diffSec < 60) return `${diffSec}s ago`;
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.floor(diffHr / 24);
  return `${diffDay}d ago`;
}

function useAlertFeed() {
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [hasNew, setHasNew] = useState(false);
  const [cues, setCues] = useState(() => getAlertCues());
  const lastSeenRef = useRef<number | null>(null);
  const inflightRef = useRef(false);

  useEffect(() => {
    setCues(getAlertCues());
    return onAlertCuesChange(setCues);
  }, []);

  useEffect(() => {
    let timer: number | undefined;
    const fetchAlerts = async () => {
      if (inflightRef.current) return;
      inflightRef.current = true;
      try {
        const resp = await getAlerts({ status: 'OPEN', page: 1, page_size: 10 });
        const items = Array.isArray(resp) ? resp : resp.items;
        if (items.length > 0) {
          const newest = items[0];
          const newestEpoch = alertEpoch(newest);
          const qualifies =
            severityRank(newest.severity_final as Severity) >= severityRank(cues.minSeverity) &&
            (!cues.quietHoursEnabled ||
              !isQuietNow(cues.quietHoursStart, cues.quietHoursEnd));
          if (
            newestEpoch &&
            lastSeenRef.current &&
            newestEpoch > lastSeenRef.current &&
            qualifies
          ) {
            if (cues.visual) {
              setHasNew(true);
              window.dispatchEvent(
                new CustomEvent('pdsnetra-alert-new', { detail: { severity: newest.severity_final } })
              );
              setTimeout(() => setHasNew(false), 2400);
            }
            if (cues.sound) playBeep(newest.severity_final as Severity);
          }
          if (newestEpoch) {
            lastSeenRef.current = newestEpoch;
          }
        }
        setAlerts(items);
      } catch {
        // Ignore polling errors
      } finally {
        inflightRef.current = false;
      }
    };
    fetchAlerts();
    timer = window.setInterval(fetchAlerts, POLL_INTERVAL_MS);
    return () => {
      if (timer) window.clearInterval(timer);
    };
  }, [cues.minSeverity, cues.quietHoursEnabled, cues.quietHoursEnd, cues.quietHoursStart, cues.sound, cues.visual]);

  const quietActive =
    cues.quietHoursEnabled && isQuietNow(cues.quietHoursStart, cues.quietHoursEnd);

  return { alerts, hasNew, cues, quietActive };
}

export function LiveRail() {
  const { alerts, hasNew, cues, quietActive } = useAlertFeed();
  const [uiPrefs, setUiPrefsState] = useState(() => getUiPrefs());
  const [mounted, setMounted] = useState(false);
  const [scope, setScope] = useState<'ALL' | 'GODOWN' | 'CAMERA'>('ALL');
  const [scopeGodown, setScopeGodown] = useState('');
  const [scopeCamera, setScopeCamera] = useState('');
  const [dismissedIds, setDismissedIds] = useState<Array<string | number>>([]);

  useEffect(() => {
    setUiPrefsState(getUiPrefs());
    setMounted(true);
    return onUiPrefsChange(setUiPrefsState);
  }, []);

  const sortedAlerts = useMemo(() => {
    const copy = [...alerts];
    copy.sort((a, b) => {
      const priDiff = alertPriority(b) - alertPriority(a);
      if (priDiff !== 0) return priDiff;
      const sevDiff = severityRank(b.severity_final as Severity) - severityRank(a.severity_final as Severity);
      if (sevDiff !== 0) return sevDiff;
      return (alertEpoch(b) ?? 0) - (alertEpoch(a) ?? 0);
    });
    return copy;
  }, [alerts]);

  const godownOptions = useMemo(() => {
    const set = new Set<string>();
    for (const alert of sortedAlerts) {
      if (alert.godown_id) set.add(alert.godown_id);
    }
    return Array.from(set).sort();
  }, [sortedAlerts]);

  const cameraOptions = useMemo(() => {
    const set = new Set<string>();
    for (const alert of sortedAlerts) {
      if (alert.camera_id) set.add(alert.camera_id);
    }
    return Array.from(set).sort();
  }, [sortedAlerts]);

  useEffect(() => {
    if (scope === 'GODOWN' && !scopeGodown && godownOptions.length > 0) {
      setScopeGodown(godownOptions[0]);
    }
    if (scope === 'CAMERA' && !scopeCamera && cameraOptions.length > 0) {
      setScopeCamera(cameraOptions[0]);
    }
  }, [scope, scopeGodown, scopeCamera, godownOptions, cameraOptions]);

  const filteredAlerts = useMemo(() => {
    let list = sortedAlerts.filter((a) => !dismissedIds.includes(a.id));
    if (scope === 'GODOWN' && scopeGodown) {
      list = list.filter((a) => a.godown_id === scopeGodown);
    }
    if (scope === 'CAMERA' && scopeCamera) {
      list = list.filter((a) => a.camera_id === scopeCamera);
    }
    return list;
  }, [sortedAlerts, dismissedIds, scope, scopeGodown, scopeCamera]);

  const timeline = useMemo(() => filteredAlerts.slice(0, 8), [filteredAlerts]);

  if (!mounted || !uiPrefs.railOpen) {
    return null;
  }

  return (
    <aside className="hidden xl:flex xl:flex-col xl:w-80 px-6 py-6 gap-4">
      <div className="hud-card p-4 sticky top-24">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-xs uppercase tracking-[0.3em] text-slate-400">Live Timeline</div>
            <div className="text-lg font-semibold font-display text-slate-100">Active Alerts</div>
          </div>
          <span className={`pulse-dot ${hasNew ? 'pulse-warning' : 'pulse-info'}`} />
        </div>
        <div className="mt-3 flex flex-wrap gap-2 text-[10px] uppercase tracking-[0.3em] text-slate-400">
          <span className="hud-pill">Threshold: {cues.minSeverity}</span>
          {quietActive && <span className="hud-pill">Quiet hours</span>}
        </div>
        <div className="mt-3 space-y-2 text-[11px] text-slate-400">
          <div className="flex items-center gap-2">
            <span className="text-slate-400">Scope</span>
            <select
              className="rounded-full border border-white/20 bg-white/10 px-2 py-1 text-[10px] uppercase tracking-[0.3em] text-slate-200"
              value={scope}
              onChange={(e) => setScope(e.target.value as 'ALL' | 'GODOWN' | 'CAMERA')}
            >
              <option value="ALL">All</option>
              <option value="GODOWN">Godown</option>
              <option value="CAMERA">Camera</option>
            </select>
          </div>
          {scope === 'GODOWN' ? (
            <select
              className="w-full rounded-full border border-white/20 bg-white/10 px-3 py-1 text-xs text-slate-200"
              value={scopeGodown}
              onChange={(e) => setScopeGodown(e.target.value)}
            >
              {godownOptions.map((g) => (
                <option key={g} value={g}>
                  {g}
                </option>
              ))}
            </select>
          ) : null}
          {scope === 'CAMERA' ? (
            <select
              className="w-full rounded-full border border-white/20 bg-white/10 px-3 py-1 text-xs text-slate-200"
              value={scopeCamera}
              onChange={(e) => setScopeCamera(e.target.value)}
            >
              {cameraOptions.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          ) : null}
        </div>
        <button
          className="mt-3 inline-flex items-center gap-2 text-[11px] uppercase tracking-[0.3em] text-slate-400"
          onClick={() => setUiPrefs({ railOpen: false })}
        >
          Hide rail
        </button>
      </div>

      <div className="hud-card p-4 space-y-3">
        {timeline.length === 0 && (
          <div className="text-sm text-slate-400">No open alerts right now.</div>
        )}
        {timeline.map((alert) => (
          <div key={alert.id} className="alert-toast p-3">
            <div className="flex items-center justify-between">
              <div className="text-xs uppercase tracking-[0.3em] text-slate-400">Alert</div>
              <span className={`pulse-dot ${alert.severity_final === 'critical' ? 'pulse-critical' : alert.severity_final === 'warning' ? 'pulse-warning' : 'pulse-info'}`} />
            </div>
            <div className="mt-1 text-sm font-semibold text-white">
              {alertTitle(alert)}
            </div>
            {alertDetail(alert) ? (
              <div className="mt-1 text-xs text-slate-300">{alertDetail(alert)}</div>
            ) : null}
            {alert.key_meta?.reason ? (
              <div className="mt-1 text-xs text-slate-300">Reason: {alert.key_meta.reason}</div>
            ) : null}
            <div className="mt-1 text-xs text-slate-400">
              {(alert.camera_id ?? '-') + ' • ' + (alert.godown_name ?? alert.godown_id)} • {timeAgo(alert)}
            </div>
            <div className="mt-1 text-xs text-slate-500">Events: {alert.count_events ?? '-'}</div>
            <button
              className="mt-2 text-[10px] uppercase tracking-[0.3em] text-slate-400"
              onClick={async () => {
                setDismissedIds((prev) => [...prev, alert.id]);
                try {
                  await acknowledgeAlert(alert.id);
                } catch {
                  // Ignore ack failures; the next poll will rehydrate if still open.
                }
              }}
            >
              Acknowledge
            </button>
          </div>
        ))}
      </div>
    </aside>
  );
}

export function MobileRail() {
  const { alerts, hasNew, quietActive } = useAlertFeed();
  const [uiPrefs, setUiPrefsState] = useState(() => getUiPrefs());
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setUiPrefsState(getUiPrefs());
    setMounted(true);
    return onUiPrefsChange(setUiPrefsState);
  }, []);

  if (!mounted || !uiPrefs.railOpen) return null;
  const latest = alerts[0];

  if (!latest) return null;

  return (
    <div className="mobile-rail xl:hidden">
      <div className="mobile-rail-inner">
        <div className="flex items-center gap-3">
          <span className={`pulse-dot ${hasNew ? 'pulse-warning' : latest.severity_final === 'critical' ? 'pulse-critical' : latest.severity_final === 'warning' ? 'pulse-warning' : 'pulse-info'}`} />
          <div className="text-xs uppercase tracking-[0.3em] text-slate-300">Live alert</div>
          {quietActive && <div className="text-[10px] uppercase tracking-[0.3em] text-slate-400">Quiet</div>}
        </div>
        <div className="text-sm font-semibold text-white truncate">
          {alertTitle(latest)}
        </div>
        {alertDetail(latest) ? (
          <div className="text-xs text-slate-300 truncate">{alertDetail(latest)}</div>
        ) : null}
        {latest.key_meta?.reason ? (
          <div className="text-xs text-slate-300 truncate">Reason: {latest.key_meta.reason}</div>
        ) : null}
        <div className="text-xs text-slate-400 truncate">
          {(latest.camera_id ?? '-') + ' • ' + (latest.godown_name ?? latest.godown_id)} • {formatUtc(latest.end_time ?? latest.start_time)}
        </div>
      </div>
    </div>
  );
}
