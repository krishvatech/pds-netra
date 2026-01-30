'use client';

import { useEffect, useMemo, useState } from 'react';
import { getAnprCsvEvents } from '@/lib/api';
import type { AnprCsvEventsResponse } from '@/lib/types';
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
  { label: 'BLACKLIST', value: 'BLACKLIST' }
];

function statusBadge(status: string) {
  if (status === 'VERIFIED')
    return <Badge className="bg-green-100 text-green-800 border border-green-200">VERIFIED</Badge>;
  if (status === 'BLACKLIST')
    return <Badge className="bg-red-100 text-red-800 border border-red-200">BLACKLIST</Badge>;
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
  const [godownId, setGodownId] = useState('GDN_001');
  const [cameraId, setCameraId] = useState('');
  const [matchStatus, setMatchStatus] = useState('');
  const [limit, setLimit] = useState(500);

  const [data, setData] = useState<AnprCsvEventsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  // 🔁 Background refresh (no flicker)
  useEffect(() => {
    let alive = true;

    async function load() {
      try {
        const resp = await getAnprCsvEvents({
          godown_id: godownId,
          camera_id: cameraId || undefined,
          match_status: matchStatus || undefined,
          limit
        });
        if (alive) setData(resp);
      } catch (e: any) {
        if (alive) setError(e?.message || 'Failed to load ANPR data');
      }
    }

    load();
    const t = setInterval(load, 3000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, [godownId, cameraId, matchStatus, limit]);

  // 🔥 BUILD SESSIONS FROM EVENTS
  const sessions = useMemo(() => {
    if (!data?.events) return [];

    const byPlate: Record<string, any[]> = {};
    for (const e of data.events) {
      if (!byPlate[e.plate_text]) byPlate[e.plate_text] = [];
      byPlate[e.plate_text].push(e);
    }

    const now = Date.now();
    const rows: any[] = [];

    Object.entries(byPlate).forEach(([plate, events]) => {
      events.sort(
        (a, b) => new Date(a.timestamp_utc).getTime() - new Date(b.timestamp_utc).getTime()
      );

      const entry = events[0];
      const last = events[events.length - 1];

      const entryTs = new Date(entry.timestamp_utc);
      const lastTs = new Date(last.timestamp_utc);

      const isActive = now - lastTs.getTime() <= SESSION_TIMEOUT_MS;

      rows.push({
        plate,
        status: last.match_status,
        entryTime: entry.timestamp_local,
        exitTime: isActive ? null : last.timestamp_local,
        duration: isActive ? null : formatDuration(lastTs.getTime() - entryTs.getTime()),
        confidence: Math.max(...events.map(e => e.combined_conf || 0)),
        camera: last.camera_id,
        session: isActive ? 'ACTIVE' : 'CLOSED'
      });
    });

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
            <Input value={godownId} onChange={(e) => setGodownId(e.target.value)} />
          </div>

          <div>
            <Label>Camera</Label>
            <Input value={cameraId} onChange={(e) => setCameraId(e.target.value)} />
          </div>

          <div>
            <Label>Status</Label>
            <Select value={matchStatus} onChange={(e) => setMatchStatus(e.target.value)} options={statusOptions} />
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
                sessions.map((s) => (
                  <TR key={s.plate}>
                    <TD className="font-semibold">{s.plate}</TD>
                    <TD>{statusBadge(s.status)}</TD>
                    <TD>{s.entryTime}</TD>
                    <TD>{s.exitTime ?? '—'}</TD>
                    <TD>{s.duration ?? '—'}</TD>
                    <TD>{s.confidence.toFixed(2)}</TD>
                    <TD>{s.camera}</TD>
                    <TD>
                      <Badge className={s.session === 'ACTIVE'
                        ? 'bg-blue-100 text-blue-800 border border-blue-200'
                        : 'bg-slate-100 text-slate-700 border border-slate-200'}>
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
