'use client';

import { useEffect, useMemo, useState } from 'react';
import { getAlerts } from '@/lib/api';
import type { AlertItem, AlertStatus, Severity } from '@/lib/types';
import { AlertsTable } from '@/components/tables/AlertsTable';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { Label } from '@/components/ui/label';
import { ErrorBanner } from '@/components/ui/error-banner';

const severityOptions = [
  { label: 'All severities', value: '' },
  { label: 'Critical', value: 'critical' },
  { label: 'Warning', value: 'warning' },
  { label: 'Info', value: 'info' }
];

const statusOptions = [
  { label: 'All statuses', value: '' },
  { label: 'Open', value: 'OPEN' },
  { label: 'Closed', value: 'CLOSED' }
];

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [godownId, setGodownId] = useState('');
  const [district, setDistrict] = useState('');
  const [severity, setSeverity] = useState<string>('');
  const [status, setStatus] = useState<string>('OPEN');
  const [dateFrom, setDateFrom] = useState<string>('');
  const [dateTo, setDateTo] = useState<string>('');
  const [error, setError] = useState<string | null>(null);

  const tickerItems = useMemo(() => {
    const slice = alerts.slice(0, 8);
    return slice.length > 0 ? slice : [];
  }, [alerts]);

  const pulseClass = (sev: Severity) => {
    if (sev === 'critical') return 'pulse-dot pulse-critical';
    if (sev === 'warning') return 'pulse-dot pulse-warning';
    return 'pulse-dot pulse-info';
  };

  const activeFilters = useMemo(() => {
    const chips: string[] = [];
    if (godownId.trim()) chips.push(`Godown: ${godownId.trim()}`);
    if (district.trim()) chips.push(`District: ${district.trim()}`);
    if (severity) chips.push(`Severity: ${severity}`);
    if (status) chips.push(`Status: ${status}`);
    if (dateFrom) chips.push(`From: ${dateFrom}`);
    if (dateTo) chips.push(`To: ${dateTo}`);
    return chips;
  }, [godownId, district, severity, status, dateFrom, dateTo]);

  const params = useMemo(() => {
    const p: Record<string, any> = {
      page: 1,
      page_size: 50
    };
    if (godownId.trim()) p.godown_id = godownId.trim();
    if (district.trim()) p.district = district.trim();
    if (severity) p.severity = severity as Severity;
    if (status) p.status = status as AlertStatus;
    if (dateFrom) p.date_from = new Date(dateFrom).toISOString();
    if (dateTo) p.date_to = new Date(dateTo).toISOString();
    return p;
  }, [godownId, district, severity, status, dateFrom, dateTo]);

  const stats = useMemo(() => {
    const total = alerts.length;
    const critical = alerts.filter((a) => a.severity_final === 'critical').length;
    const warning = alerts.filter((a) => a.severity_final === 'warning').length;
    return { total, critical, warning };
  }, [alerts]);

  useEffect(() => {
    let mounted = true;
    (async () => {
      setError(null);
      try {
        const resp = await getAlerts(params);
        if (mounted) setAlerts(resp.items);
      } catch (e) {
        if (mounted) setError(e instanceof Error ? e.message : 'Failed to load alerts');
      }
    })();
    return () => {
      mounted = false;
    };
  }, [params]);

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="space-y-2">
          <div className="hud-pill">
            <span className="pulse-dot pulse-warning" />
            Alert feed
          </div>
          <div className="text-4xl font-semibold font-display tracking-tight text-slate-100 drop-shadow">
            Alert Command Feed
          </div>
          <div className="text-sm text-slate-300">Filter and review alerts across godowns.</div>
        </div>
        <div className="intel-banner">Live visibility</div>
      </div>

      <div className="metric-grid">
        <div className="hud-card p-5 animate-fade-up">
          <div className="hud-label">Open alerts</div>
          <div className="hud-value mt-2">{stats.total}</div>
          <div className="text-xs text-slate-400 mt-2">All statuses in current filter</div>
        </div>
        <div className="hud-card p-5 animate-fade-up">
          <div className="hud-label">Critical</div>
          <div className="hud-value mt-2">{stats.critical}</div>
          <div className="text-xs text-slate-400 mt-2">Immediate escalation required</div>
        </div>
        <div className="hud-card p-5 animate-fade-up">
          <div className="hud-label">Warning</div>
          <div className="hud-value mt-2">{stats.warning}</div>
          <div className="text-xs text-slate-400 mt-2">Requires supervision</div>
        </div>
      </div>

      <Card className="animate-fade-up hud-card">
        <CardHeader>
          <div className="text-lg font-semibold font-display">Filters</div>
          <div className="text-sm text-slate-300">Refine by godown, district, severity, and time window.</div>
        </CardHeader>
        <CardContent>
        {error && <ErrorBanner message={error} onRetry={() => window.location.reload()} />}

        {tickerItems.length > 0 && (
          <div className="ticker mb-4">
            <div className="ticker-track">
              {[...tickerItems, ...tickerItems].map((alert, idx) => (
                <div key={`${alert.id}-${idx}`} className="ticker-chip">
                  <span className={pulseClass(alert.severity_final as Severity)} />
                  {alert.godown_name ?? alert.godown_id} • {alert.alert_type.replaceAll('_', ' ')}
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-6 gap-3 mb-4">
          <div className="md:col-span-2">
            <Label>Godown ID</Label>
            <Input value={godownId} onChange={(e) => setGodownId(e.target.value)} placeholder="GDN_001" />
          </div>
          <div className="md:col-span-2">
            <Label>District</Label>
            <Input value={district} onChange={(e) => setDistrict(e.target.value)} placeholder="Surat" />
          </div>
          <div>
            <Label>Severity</Label>
            <Select value={severity} onChange={(e) => setSeverity(e.target.value)} options={severityOptions} />
          </div>
          <div>
            <Label>Status</Label>
            <Select value={status} onChange={(e) => setStatus(e.target.value)} options={statusOptions} />
          </div>

          <div className="md:col-span-3">
            <Label>Date from</Label>
            <Input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
          </div>
          <div className="md:col-span-3">
            <Label>Date to</Label>
            <Input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
          </div>
        </div>

        {activeFilters.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-4">
            {activeFilters.map((chip) => (
              <span key={chip} className="hud-pill">
                {chip}
              </span>
            ))}
          </div>
        )}

        {alerts.length > 0 && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-3 mb-5 stagger">
            {alerts.slice(0, 6).map((alert) => (
              <div key={alert.id} className="incident-card p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="text-xs uppercase tracking-[0.3em] text-slate-400">Live alert</div>
                    <div className="mt-1 text-sm font-semibold text-white">
                      {alert.alert_type.replaceAll('_', ' ')}
                    </div>
                    <div className="text-xs text-slate-400 mt-1">{alert.godown_name ?? alert.godown_id}</div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={pulseClass(alert.severity_final as Severity)} />
                    <span className="text-xs uppercase tracking-[0.2em] text-slate-300">{alert.severity_final}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        <AlertsTable alerts={alerts} />
        </CardContent>
      </Card>
    </div>
  );
}
