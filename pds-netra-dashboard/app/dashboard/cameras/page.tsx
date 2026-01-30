'use client';

import { useEffect, useMemo, useState } from 'react';
import type { CameraInfo, CameraModules } from '@/lib/types';
import { getCameras } from '@/lib/api';
import { getUser } from '@/lib/auth';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select } from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Table, TBody, TD, TH, THead, TR } from '@/components/ui/table';
import { ErrorBanner } from '@/components/ui/error-banner';
import { ToastStack, type ToastItem } from '@/components/ui/toast';

const MOCK_MODE = process.env.NEXT_PUBLIC_MOCK_MODE === 'true';

const mockCameras: CameraInfo[] = [
  {
    camera_id: 'CAM_GATE_1',
    label: 'Gate ANPR',
    role: 'GATE_ANPR',
    rtsp_url: 'rtsp://example/gate',
    is_active: true,
    modules: {
      anpr_enabled: true,
      gate_entry_exit_enabled: true,
      person_after_hours_enabled: false,
      animal_detection_enabled: false,
      fire_detection_enabled: false,
      health_monitoring_enabled: true
    }
  },
  {
    camera_id: 'CAM_AISLE_3',
    label: 'Aisle 3',
    role: 'SECURITY',
    rtsp_url: 'rtsp://example/aisle',
    is_active: true,
    modules: {
      anpr_enabled: false,
      gate_entry_exit_enabled: false,
      person_after_hours_enabled: true,
      animal_detection_enabled: true,
      fire_detection_enabled: false,
      health_monitoring_enabled: true
    }
  }
];

const moduleLabels: Array<{ key: keyof CameraModules; label: string }> = [
  { key: 'anpr_enabled', label: 'ANPR' },
  { key: 'gate_entry_exit_enabled', label: 'Gate Entry/Exit' },
  { key: 'person_after_hours_enabled', label: 'After-hours' },
  { key: 'animal_detection_enabled', label: 'Animals' },
  { key: 'fire_detection_enabled', label: 'Fire' },
  { key: 'health_monitoring_enabled', label: 'Health' }
];

function defaultModulesForRole(role?: string | null): CameraModules {
  const normalized = (role ?? '').toUpperCase();
  if (normalized === 'GATE_ANPR') {
    return {
      anpr_enabled: true,
      gate_entry_exit_enabled: true,
      person_after_hours_enabled: false,
      animal_detection_enabled: false,
      fire_detection_enabled: false,
      health_monitoring_enabled: true
    };
  }
  if (normalized === 'HEALTH_ONLY') {
    return {
      anpr_enabled: false,
      gate_entry_exit_enabled: false,
      person_after_hours_enabled: false,
      animal_detection_enabled: false,
      fire_detection_enabled: false,
      health_monitoring_enabled: true
    };
  }
  return {
    anpr_enabled: false,
    gate_entry_exit_enabled: false,
    person_after_hours_enabled: true,
    animal_detection_enabled: true,
    fire_detection_enabled: true,
    health_monitoring_enabled: true
  };
}

function formatRole(role?: string | null): string {
  if (!role) return 'SECURITY';
  return role.replaceAll('_', ' ');
}

export default function CamerasPage() {
  const [cameras, setCameras] = useState<CameraInfo[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [filterGodown, setFilterGodown] = useState('');
  const [filterRole, setFilterRole] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [query, setQuery] = useState('');
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  useEffect(() => {
    if (!filterGodown) {
      const user = getUser();
      if (user?.godown_id) setFilterGodown(String(user.godown_id));
    }
  }, [filterGodown]);

  const roleOptions = useMemo(
    () => [
      { label: 'All roles', value: '' },
      { label: 'GATE_ANPR', value: 'GATE_ANPR' },
      { label: 'SECURITY', value: 'SECURITY' },
      { label: 'HEALTH_ONLY', value: 'HEALTH_ONLY' }
    ],
    []
  );

  const statusOptions = useMemo(
    () => [
      { label: 'All', value: '' },
      { label: 'Active', value: 'active' },
      { label: 'Inactive', value: 'inactive' }
    ],
    []
  );

  function pushToast(toast: Omit<ToastItem, 'id'>) {
    const id = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    setToasts((items) => [...items, { id, ...toast }]);
  }

  const apiFilters = useMemo(() => {
    const p: Record<string, string | boolean> = {};
    if (filterGodown.trim()) p.godown_id = filterGodown.trim();
    if (filterRole) p.role = filterRole;
    if (filterStatus) p.is_active = filterStatus === 'active';
    return p;
  }, [filterGodown, filterRole, filterStatus]);

  async function loadCameras(options?: { showToast?: boolean }) {
    setError(null);
    setLoading(true);
    try {
      if (MOCK_MODE) {
        setCameras(mockCameras);
        if (options?.showToast) {
          pushToast({ type: 'info', title: 'Mock refreshed', message: `Loaded ${mockCameras.length} cameras` });
        }
        return;
      }
      const rows = await getCameras(apiFilters);
      setCameras(rows ?? []);
      if (options?.showToast) {
        pushToast({ type: 'info', title: 'Cameras refreshed', message: `Loaded ${rows?.length ?? 0} cameras` });
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load cameras');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    let mounted = true;
    (async () => {
      if (!mounted) return;
      await loadCameras();
    })();
    return () => {
      mounted = false;
    };
  }, [apiFilters]);

  const filtered = useMemo(() => {
    const term = query.trim().toLowerCase();
    if (!term) return cameras;
    return cameras.filter((camera) => {
      const label = `${camera.camera_id} ${camera.label ?? ''}`.toLowerCase();
      return label.includes(term);
    });
  }, [cameras, query]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Cameras</h1>
          <p className="text-sm text-slate-500">Role-based routing for ANPR and security pipelines.</p>
        </div>
        <Button onClick={() => loadCameras({ showToast: true })} disabled={loading}>
          {loading ? 'Refreshing...' : 'Refresh'}
        </Button>
      </div>

      <Card className="bg-white/80 border-white/40 shadow-sm">
        <CardHeader className="pb-3">
          <div className="grid gap-3 md:grid-cols-4">
            <div>
              <Label>Godown ID</Label>
              <Input value={filterGodown} onChange={(e) => setFilterGodown(e.target.value)} placeholder="Auto (from login)" />
            </div>
            <div>
              <Label>Role</Label>
              <Select value={filterRole} onChange={(e) => setFilterRole(e.target.value)} options={roleOptions} />
            </div>
            <div>
              <Label>Status</Label>
              <Select value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)} options={statusOptions} />
            </div>
            <div>
              <Label>Search</Label>
              <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="CAM_GATE_1" />
            </div>
          </div>
        </CardHeader>
        <CardContent className="pt-0">
          {error ? <ErrorBanner message={error} /> : null}
          <div className="overflow-x-auto rounded-2xl border border-white/70 bg-white/70">
            <Table>
              <THead>
                <TR>
                  <TH>Camera</TH>
                  <TH>Godown</TH>
                  <TH>Role</TH>
                  <TH>Modules</TH>
                  <TH>Status</TH>
                </TR>
              </THead>
              <TBody>
                {filtered.map((camera) => {
                  const modules = camera.modules ?? defaultModulesForRole(camera.role);
                  const enabledModules = moduleLabels.filter((entry) => modules?.[entry.key]);
                  const derived = camera.modules == null;
                  return (
                    <TR key={camera.camera_id}>
                      <TD>
                        <div className="font-semibold text-slate-900">{camera.label ?? camera.camera_id}</div>
                        <div className="text-xs text-slate-500">{camera.camera_id}</div>
                      </TD>
                      <TD className="text-sm text-slate-700">{camera.godown_id ?? '-'}</TD>
                      <TD>
                        <Badge className="bg-slate-100 text-slate-800 border-slate-200">
                          {formatRole(camera.role)}
                        </Badge>
                      </TD>
                      <TD>
                        <div className="flex flex-wrap gap-1">
                          {enabledModules.length ? (
                            enabledModules.map((entry) => (
                              <Badge key={entry.key} variant="outline" className="border-slate-200 text-slate-700">
                                {entry.label}
                              </Badge>
                            ))
                          ) : (
                            <span className="text-xs text-slate-400">No modules</span>
                          )}
                        </div>
                        {derived ? (
                          <div className="text-[11px] text-slate-400 mt-1">Derived from role defaults</div>
                        ) : null}
                      </TD>
                      <TD>
                        <Badge className={camera.is_active ? 'bg-emerald-100 text-emerald-800 border-emerald-200' : 'bg-slate-100 text-slate-600 border-slate-200'}>
                          {camera.is_active ? 'Active' : 'Inactive'}
                        </Badge>
                      </TD>
                    </TR>
                  );
                })}
                {!filtered.length ? (
                  <TR>
                    <TD colSpan={5} className="text-center text-sm text-slate-500 py-6">
                      No cameras found for the selected filters.
                    </TD>
                  </TR>
                ) : null}
              </TBody>
            </Table>
          </div>
        </CardContent>
      </Card>
      <ToastStack items={toasts} onDismiss={(id) => setToasts((items) => items.filter((t) => t.id !== id))} />
    </div>
  );
}
