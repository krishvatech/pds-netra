'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { getAlerts } from '@/lib/api';
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

function alertEpoch(alert: AlertItem): number | null {
  const ts = alert.end_time ?? alert.start_time;
  if (!ts) return null;
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return null;
  return d.getTime();
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

  useEffect(() => {
    setUiPrefsState(getUiPrefs());
    setMounted(true);
    return onUiPrefsChange(setUiPrefsState);
  }, []);

  const timeline = useMemo(() => alerts.slice(0, 8), [alerts]);

  if (!mounted || !uiPrefs.railOpen) {
    return null;
  }

  return (
    <aside className="hidden xl:flex xl:flex-col xl:w-80 px-6 py-6 gap-4">
      <div className="glass-panel rounded-2xl p-4 sticky top-24">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-xs uppercase tracking-[0.3em] text-slate-500">Live Timeline</div>
            <div className="text-lg font-semibold font-display">Active Alerts</div>
          </div>
          <span className={`pulse-dot ${hasNew ? 'pulse-warning' : 'pulse-info'}`} />
        </div>
        <div className="mt-3 flex flex-wrap gap-2 text-[10px] uppercase tracking-[0.3em] text-slate-500">
          <span className="badge-soft px-2 py-1 rounded-full">Threshold: {cues.minSeverity}</span>
          {quietActive && <span className="badge-soft px-2 py-1 rounded-full">Quiet hours</span>}
        </div>
        <button
          className="mt-3 inline-flex items-center gap-2 text-[11px] uppercase tracking-[0.3em] text-slate-500"
          onClick={() => setUiPrefs({ railOpen: false })}
        >
          Hide rail
        </button>
      </div>

      <div className="glass-panel rounded-2xl p-4 space-y-3">
        {timeline.length === 0 && (
          <div className="text-sm text-slate-500">No open alerts right now.</div>
        )}
        {timeline.map((alert) => (
          <div key={alert.id} className="alert-toast p-3">
            <div className="flex items-center justify-between">
              <div className="text-xs uppercase tracking-[0.3em] text-slate-400">Alert</div>
              <span className={`pulse-dot ${alert.severity_final === 'critical' ? 'pulse-critical' : alert.severity_final === 'warning' ? 'pulse-warning' : 'pulse-info'}`} />
            </div>
            <div className="mt-1 text-sm font-semibold text-white">
              {humanAlertType(alert.alert_type)}
            </div>
            <div className="mt-1 text-xs text-slate-400">
              {alert.godown_name ?? alert.godown_id} • {formatUtc(alert.end_time ?? alert.start_time)}
            </div>
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
          {humanAlertType(latest.alert_type)}
        </div>
        <div className="text-xs text-slate-400 truncate">
          {latest.godown_name ?? latest.godown_id} • {formatUtc(latest.end_time ?? latest.start_time)}
        </div>
      </div>
    </div>
  );
}
