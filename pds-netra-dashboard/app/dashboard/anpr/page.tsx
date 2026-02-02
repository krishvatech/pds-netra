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

export default function AnprDashboardPage() {
  const [godownId, setGodownId] = useState('');
  const [godowns, setGodowns] = useState<GodownListItem[]>([]);
  const [cameras, setCameras] = useState<CameraInfo[]>([]);
  const [cameraId, setCameraId] = useState('');
  const [matchStatus, setMatchStatus] = useState('');
  const [limit, setLimit] = useState(500);

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

  // 🔥 BUILD SESSIONS FROM EVENTS (DB-backed)
  const sessions = useMemo(() => {
    if (!data?.events) return [];

    const byPlate: Record<string, any[]> = {};
    for (const e of data.events) {
      if (!e?.plate_text) continue;
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

  return (
    <div className="space-y-4">
      <div className="text-xl font-semibold">ANPR Vehicle Sessions</div>

      {error && <ErrorBanner message={error} />}

      <Card>
        <CardHeader>
          <div className="font-medium">Filters</div>
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

      <Card>
        <CardHeader>
          <div className="font-medium">Vehicle Entry / Exit Sessions</div>
        </CardHeader>
        <CardContent className="overflow-auto">
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
              {sessions.length === 0 ? (
                <TR>
                  <TD colSpan={8} className="text-sm text-slate-500">
                    No vehicle sessions
                  </TD>
                </TR>
              ) : (
                sessions.map((s: any) => (
                  <TR key={`${s.plate}-${s.camera}`}>
                    <TD className="font-semibold">{s.plate}</TD>
                    <TD>{statusBadge(s.status)}</TD>
                    <TD>{s.entryTime}</TD>
                    <TD>{s.exitTime ?? '—'}</TD>
                    <TD>{s.duration ?? '—'}</TD>
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
        </CardContent>
      </Card>
    </div>
  );
}
