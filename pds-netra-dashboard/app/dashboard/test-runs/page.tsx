'use client';

import { useEffect, useMemo, useState } from 'react';
import {
  activateTestRun,
  createTestRun,
  deleteTestRun,
  getGodownDetail,
  getGodowns,
  getTestRuns
} from '@/lib/api';
import type { CameraInfo, GodownListItem, TestRunItem } from '@/lib/types';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { ErrorBanner } from '@/components/ui/error-banner';
import { Table, THead, TBody, TR, TH, TD } from '@/components/ui/table';
import Link from 'next/link';
import { formatUtc } from '@/lib/formatters';

export default function TestRunsPage() {
  const [godowns, setGodowns] = useState<GodownListItem[]>([]);
  const [cameras, setCameras] = useState<CameraInfo[]>([]);
  const [runs, setRuns] = useState<TestRunItem[]>([]);
  const [godownId, setGodownId] = useState('');
  const [cameraId, setCameraId] = useState('');
  const [zoneId, setZoneId] = useState('');
  const [runName, setRunName] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [lastRun, setLastRun] = useState<TestRunItem | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const data = await getGodowns();
        if (mounted) setGodowns(Array.isArray(data) ? data : data.items);
      } catch (e) {
        if (mounted) setError(e instanceof Error ? e.message : 'Failed to load godowns');
      }
    })();
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const data = await getTestRuns();
        if (mounted) setRuns(data);
      } catch (e) {
        if (mounted) setError(e instanceof Error ? e.message : 'Failed to load test runs');
      }
    })();
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    if (!godownId) {
      setCameras([]);
      setCameraId('');
      return;
    }
    let mounted = true;
    (async () => {
      try {
        const detail = await getGodownDetail(godownId);
        if (mounted) setCameras(detail.cameras ?? []);
      } catch (e) {
        if (mounted) setError(e instanceof Error ? e.message : 'Failed to load cameras');
      }
    })();
    return () => {
      mounted = false;
    };
  }, [godownId]);

  const godownOptions = useMemo(() => {
    return [
      { label: 'Select godown', value: '' },
      ...godowns.map((g) => ({ label: `${g.name ?? g.godown_id} (${g.godown_id})`, value: g.godown_id }))
    ];
  }, [godowns]);

  const cameraOptions = useMemo(() => {
    return [
      { label: 'Select camera', value: '' },
      ...cameras.map((c) => ({ label: c.label ? `${c.label} (${c.camera_id})` : c.camera_id, value: c.camera_id }))
    ];
  }, [cameras]);

  const submitDisabled = loading || !godownId || !cameraId || !file;

  const handleUpload = async () => {
    if (!file) return;
    setLoading(true);
    setError(null);
    try {
      const form = new FormData();
      form.append('file', file);
      form.append('godown_id', godownId);
      form.append('camera_id', cameraId);
      if (zoneId.trim()) form.append('zone_id', zoneId.trim());
      if (runName.trim()) form.append('run_name', runName.trim());
      const created = await createTestRun(form);
      setLastRun(created);
      setRuns((prev) => [created, ...prev]);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to upload test run');
    } finally {
      setLoading(false);
    }
  };

  const handleActivate = async (runId: string) => {
    setLoading(true);
    setError(null);
    try {
      const resp = await activateTestRun(runId);
      if (resp.run) {
        setRuns((prev) => prev.map((r) => (r.run_id === runId ? resp.run : r)));
        setLastRun(resp.run);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to activate test run');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (runId: string) => {
    const ok = window.confirm('Delete this test run and its files?');
    if (!ok) return;
    setLoading(true);
    setError(null);
    try {
      await deleteTestRun(runId);
      setRuns((prev) => prev.filter((r) => r.run_id !== runId));
      if (lastRun?.run_id === runId) setLastRun(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to delete test run');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-5">
      <Card className="animate-fade-up">
        <CardHeader>
          <div className="text-xl font-semibold font-display">Test via Upload</div>
          <div className="text-sm text-slate-600">Upload an MP4 file and activate it on the edge.</div>
        </CardHeader>
        <CardContent className="space-y-4">
          {error && <ErrorBanner message={error} onRetry={() => window.location.reload()} />}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <Label>Godown</Label>
              <Select value={godownId} onChange={(e) => setGodownId(e.target.value)} options={godownOptions} />
            </div>
            <div>
              <Label>Camera</Label>
              <Select value={cameraId} onChange={(e) => setCameraId(e.target.value)} options={cameraOptions} />
            </div>
            <div>
              <Label>Zone ID (optional)</Label>
              <Input value={zoneId} onChange={(e) => setZoneId(e.target.value)} placeholder="gate_inner" />
            </div>
            <div>
              <Label>Run name (optional)</Label>
              <Input value={runName} onChange={(e) => setRunName(e.target.value)} placeholder="Audit run - Gate 1" />
            </div>
            <div className="md:col-span-2">
              <Label>MP4 file</Label>
              <Input type="file" accept="video/mp4" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Button onClick={handleUpload} disabled={submitDisabled}>
              {loading ? 'Uploading…' : 'Upload test run'}
            </Button>
            {lastRun && (
              <Button variant="outline" onClick={() => handleActivate(lastRun.run_id)} disabled={loading}>
                Activate on Edge
              </Button>
            )}
          </div>
          {lastRun && (
            <div className="rounded-xl border border-white/60 bg-white/70 p-3 text-sm text-slate-700">
              Latest run: <span className="font-semibold">{lastRun.run_id}</span> • Status: {lastRun.status}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="text-lg font-semibold font-display">Recent test runs</div>
          <div className="text-sm text-slate-600">Track uploaded runs and activate them on edge.</div>
        </CardHeader>
        <CardContent>
          <div className="table-shell overflow-auto">
            <Table>
              <THead>
                <TR>
                  <TH>Run ID</TH>
                  <TH>Godown</TH>
                  <TH>Camera</TH>
                  <TH>Created</TH>
                  <TH>Status</TH>
                  <TH>Action</TH>
                </TR>
              </THead>
              <TBody>
                {runs.map((run) => (
                  <TR key={run.run_id}>
                    <TD>
                      <Link className="underline" href={`/dashboard/test-runs/${run.run_id}`}>
                        {run.run_id}
                      </Link>
                    </TD>
                    <TD>{run.godown_id}</TD>
                    <TD>{run.camera_id}</TD>
                    <TD>{run.created_at ? formatUtc(run.created_at) : '-'}</TD>
                    <TD>{run.status}</TD>
                    <TD>
                      <div className="flex items-center gap-2">
                        <Button variant="outline" onClick={() => handleActivate(run.run_id)} disabled={loading}>
                          Activate
                        </Button>
                        <Button variant="danger" onClick={() => handleDelete(run.run_id)} disabled={loading}>
                          Delete
                        </Button>
                      </div>
                    </TD>
                  </TR>
                ))}
                {runs.length === 0 && (
                  <TR>
                    <TD colSpan={6} className="text-slate-600">
                      No test runs yet.
                    </TD>
                  </TR>
                )}
              </TBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
