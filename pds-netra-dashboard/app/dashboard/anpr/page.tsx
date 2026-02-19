'use client';

import { useEffect, useMemo, useState } from 'react';
import { getUser } from '@/lib/auth';
import { getAnprEvents, getCameras, getGodowns } from '@/lib/api';
import type { AnprEventsResponse, CameraInfo, GodownListItem } from '@/lib/types';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Table, THead, TBody, TR, TH, TD } from '@/components/ui/table';
import { ErrorBanner } from '@/components/ui/error-banner';

const SESSION_TIMEOUT_MS = 10 * 60 * 1000; // 10 minutes

const statusOptions = [
  { label: 'All', value: '' },
  { label: 'VERIFIED', value: 'VERIFIED' },
  { label: 'NOT_VERIFIED', value: 'NOT_VERIFIED' },
  { label: 'BLACKLIST', value: 'BLACKLIST' },
  { label: 'GUESSED', value: 'GUESSED' },
  { label: 'UNKNOWN', value: 'UNKNOWN' },
];

function statusBadge(status: string) {
  const s = (status || '').toUpperCase();
  if (s === 'VERIFIED')
    return <Badge className="bg-green-100 text-green-800 border border-green-200">VERIFIED</Badge>;
  if (s === 'BLACKLIST')
    return <Badge className="bg-red-100 text-red-800 border border-red-200">BLACKLIST</Badge>;
  if (s === 'GUESSED')
    return <Badge className="bg-purple-100 text-purple-800 border border-purple-200">GUESSED</Badge>;
  if (s === 'UNKNOWN')
    return <Badge className="bg-slate-100 text-slate-800 border border-slate-200">UNKNOWN</Badge>;
  return <Badge className="bg-amber-100 text-amber-800 border border-amber-200">NOT VERIFIED</Badge>;
}

function formatDuration(ms: number) {
  const mins = Math.floor(ms / 60000);
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

function toLocalDateStr(d: Date) {
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  return `${yyyy}-${mm}-${dd}`;
}

function eventLocalDate(ev: { timestamp_local?: string; timestamp_utc?: string }) {
  if (ev.timestamp_local) return ev.timestamp_local.slice(0, 10);
  if (ev.timestamp_utc) return toLocalDateStr(new Date(ev.timestamp_utc));
  return '';
}

export default function AnprDashboardPage() {
  const [godownId, setGodownId] = useState('');
  const [godowns, setGodowns] = useState<GodownListItem[]>([]);
  const [cameras, setCameras] = useState<CameraInfo[]>([]);
  const [cameraId, setCameraId] = useState('');
  const [matchStatus, setMatchStatus] = useState('');
  const [limit, setLimit] = useState(500);
  const [nowLabel, setNowLabel] = useState('');

  const [data, setData] = useState<AnprEventsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const godownOptions = useMemo(() => {
    const opts = godowns.map((g) => ({ label: g.name || g.godown_id, value: g.godown_id }));
    if (godownId && !opts.some((o) => o.value === godownId)) {
      return [{ label: godownId, value: godownId }, ...opts];
    }
    return opts;
  }, [godowns, godownId]);

  const cameraOptions = useMemo(() => {
    const opts = (cameras || []).map((c) => ({ label: c.label || c.camera_id, value: c.camera_id }));
    const all = { label: 'All', value: '' };
    if (cameraId && !opts.some((o) => o.value === cameraId)) {
      return [all, { label: cameraId, value: cameraId }, ...opts];
    }
    return [all, ...opts];
  }, [cameras, cameraId]);

  // 🔁 Background refresh (no flicker)
  useEffect(() => {
    if (!godownId) {
      const user = getUser();
      if (user?.godown_id) setGodownId(String(user.godown_id));
    }
  }, [godownId]);

  useEffect(() => {
    let alive = true;
    async function loadGodowns() {
      try {
        const resp = await getGodowns({});
        const items = Array.isArray(resp) ? resp : resp.items;
        if (alive) setGodowns(items || []);
      } catch {
        // Non-blocking: keep page usable even if godown list fails.
      }
    }
    loadGodowns();
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    let alive = true;

    async function loadCameras() {
      if (!godownId) {
        if (alive) setCameras([]);
        return;
      }
      setCameraId('');
      try {
        const items = await getCameras({ godown_id: godownId });
        if (alive) setCameras(items || []);
      } catch {
        if (alive) setCameras([]);
      }
    }

    loadCameras();
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [godownId]);

  useEffect(() => {
    let alive = true;

    async function load() {
      if (!godownId) {
        if (alive) {
          setError(null);
          setData(null);
        }
        return;
      }
      try {
        setError(null);
        const resp = await getAnprEvents({
          godown_id: godownId,
          camera_id: cameraId || undefined,
          match_status: matchStatus || undefined,
          limit,
        });
        if (alive) setData(resp);
      } catch (e: any) {
        if (alive) setError(e?.message || 'Failed to load ANPR data');
      }
    }

    load();
    if (!godownId) {
      return () => {
        alive = false;
      };
    }
    const t = setInterval(load, 3000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, [godownId, cameraId, matchStatus, limit]);

  useEffect(() => {
    const formatter = new Intl.DateTimeFormat('en-GB', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    });
    setNowLabel(formatter.format(new Date()));
    const t = setInterval(() => {
      setNowLabel(formatter.format(new Date()));
    }, 1000);
    return () => clearInterval(t);
  }, []);

  // 🔥 BUILD SESSIONS FROM EVENTS (DB-backed)
  const sessions = useMemo(() => {
    if (!data?.events) return [];

    const todayStr = toLocalDateStr(new Date());
    const byPlate: Record<string, any[]> = {};
    for (const e of data.events) {
      if (!e?.plate_text) continue;
      if (eventLocalDate(e) !== todayStr) continue;
      if (!byPlate[e.plate_text]) byPlate[e.plate_text] = [];
      byPlate[e.plate_text].push(e);
    }

    const now = Date.now();
    const rows: any[] = [];

    Object.entries(byPlate).forEach(([plate, events]) => {
      events.sort((a, b) => new Date(a.timestamp_utc).getTime() - new Date(b.timestamp_utc).getTime());

      const entry = events[0];
      const last = events[events.length - 1];

      const entryTs = new Date(entry.timestamp_utc);
      const lastTs = new Date(last.timestamp_utc);

      const isActive = now - lastTs.getTime() <= SESSION_TIMEOUT_MS;

      // DB endpoint returns `confidence` (single number) instead of `combined_conf`
      const maxConf = Math.max(...events.map((e: any) => Number(e.confidence ?? 0)));

      rows.push({
        plate,
        status: (last.match_status || 'UNKNOWN').toUpperCase(),
        entryTime: entry.timestamp_local,
        exitTime: isActive ? null : last.timestamp_local,
        duration: isActive ? null : formatDuration(lastTs.getTime() - entryTs.getTime()),
        confidence: maxConf,
        camera: last.camera_id,
        session: isActive ? 'ACTIVE' : 'CLOSED',
      });
    });

    // newest first
    rows.sort((a, b) => String(b.entryTime).localeCompare(String(a.entryTime)));
    return rows;
  }, [data]);

  const guessedSessions = useMemo(
    () => sessions.filter((s: any) => s.status === 'GUESSED'),
    [sessions]
  );
  const liveSessions = useMemo(
    () => sessions.filter((s: any) => s.status !== 'GUESSED'),
    [sessions]
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="space-y-2">
          <div className="hud-pill">Live sessions</div>
          <div className="text-4xl font-semibold font-display tracking-tight text-slate-100 drop-shadow">
            ANPR Vehicle Sessions
          </div>
          <div className="flex flex-wrap items-center gap-2 text-xs text-slate-300">
            <span className="uppercase tracking-[0.18em] text-slate-400">Live</span>
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 shadow-[0_0_10px_rgba(52,211,153,0.7)]" />
            <span
              className="rounded-full border border-white/10 bg-white/5 px-3 py-1 font-medium text-slate-200"
              suppressHydrationWarning
            >
              {nowLabel}
            </span>
          </div>
        </div>
        <div className="hud-card p-4 min-w-[220px]">
          <div className="hud-label">Sessions</div>
          <div className="hud-value">{liveSessions.length}</div>
          <div className="text-xs text-slate-500">Refresh: 3s</div>
        </div>
      </div>

      {error && <ErrorBanner message={error} />}

      <Card className="hud-card">
        <CardHeader>
          <div className="text-lg font-semibold font-display">Filters</div>
        </CardHeader>
        <CardContent className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <div>
            <Label>Godown</Label>
            <Select
              value={godownId}
              onChange={(e) => setGodownId(e.target.value)}
              options={godownOptions}
              placeholder="Select godown..."
            />
          </div>

          <div>
            <Label>Camera</Label>
            <Select
              value={cameraId}
              onChange={(e) => setCameraId(e.target.value)}
              options={cameraOptions}
              placeholder={godownId ? 'Select camera...' : 'Select godown first'}
              disabled={!godownId}
            />
          </div>

          <div>
            <Label>Status</Label>
            <Select
              value={matchStatus}
              onChange={(e) => setMatchStatus(e.target.value)}
              options={statusOptions}
            />
          </div>

          <div>
            <Label>Limit</Label>
            <Input
              type="number"
              value={limit}
              onChange={(e) => setLimit(Math.min(2000, Number(e.target.value) || 500))}
            />
          </div>
        </CardContent>
      </Card>

      <Card className="hud-card">
        <CardHeader className="flex items-center justify-between">
          <div className="text-lg font-semibold font-display">Vehicle Entry / Exit Sessions</div>
          <div className="hud-pill">Active feed</div>
        </CardHeader>
        <CardContent>
          <div className="table-shell overflow-auto">
            <Table>
            <THead>
              <TR>
                <TH>Plate</TH>
                <TH>Status</TH>
                <TH>Entry Time</TH>
                <TH>Exit Time</TH>
                <TH>Duration</TH>
                <TH>Conf</TH>
                <TH>Camera</TH>
                <TH>Session</TH>
              </TR>
            </THead>
            <TBody>
              {liveSessions.length === 0 ? (
                <TR>
                  <TD colSpan={8} className="text-sm text-slate-500">
                    No vehicle sessions
                  </TD>
                </TR>
              ) : (
                liveSessions.map((s: any) => (
                  <TR key={`${s.plate}-${s.camera}`}>
                    <TD className="font-semibold">{s.plate}</TD>
                    <TD>{statusBadge(s.status)}</TD>
                    <TD>{s.entryTime}</TD>
                    <TD>{s.exitTime ?? 'In progress'}</TD>
                    <TD>{s.duration ?? 'In progress'}</TD>
                    <TD>{Number(s.confidence || 0).toFixed(2)}</TD>
                    <TD>{s.camera}</TD>
                    <TD>
                      <Badge
                        className={
                          s.session === 'ACTIVE'
                            ? 'bg-blue-100 text-blue-800 border border-blue-200'
                            : 'bg-slate-100 text-slate-700 border border-slate-200'
                        }
                      >
                        {s.session}
                      </Badge>
                    </TD>
                  </TR>
                ))
              )}
            </TBody>
          </Table>
          </div>
        </CardContent>
      </Card>

      <Card className="hud-card">
        <CardHeader className="flex items-center justify-between">
          <div className="text-lg font-semibold font-display">Guessed Plates</div>
          <div className="hud-pill">Confidence feed</div>
        </CardHeader>
        <CardContent>
          {guessedSessions.length === 0 ? (
            <div className="text-sm text-slate-500">No guessed plates in the last refresh window.</div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {guessedSessions.map((s: any) => (
                <div key={`${s.plate}-${s.camera}-guess`} className="rounded-xl border border-white/10 bg-white/5 p-4">
                  <div className="flex items-center justify-between">
                    <div className="text-xs uppercase tracking-[0.2em] text-slate-400">Guess</div>
                    <Badge className="bg-purple-100 text-purple-800 border border-purple-200">GUESSED</Badge>
                  </div>
                  <div className="mt-2 text-2xl font-semibold font-display text-slate-100">{s.plate}</div>
                  <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-slate-300">
                    <div>
                      <div className="text-slate-500">Confidence</div>
                      <div>{Number(s.confidence || 0).toFixed(2)}</div>
                    </div>
                    <div>
                      <div className="text-slate-500">Camera</div>
                      <div>{s.camera || '—'}</div>
                    </div>
                    <div>
                      <div className="text-slate-500">First seen</div>
                      <div>{s.entryTime || '—'}</div>
                    </div>
                    <div>
                      <div className="text-slate-500">Last seen</div>
                      <div>{s.exitTime || s.entryTime || '—'}</div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
