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
    <Card className="animate-fade-up">
      <CardHeader>
        <div className="text-xl font-semibold font-display">Alert Command Feed</div>
        <div className="text-sm text-slate-600">Filter and review alerts across godowns.</div>
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
              <span key={chip} className="badge-soft rounded-full px-3 py-1 text-[11px] uppercase tracking-[0.2em] text-slate-600">
                {chip}
              </span>
            ))}
          </div>
        )}

        {alerts.length > 0 && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-3 mb-5 stagger">
            {alerts.slice(0, 6).map((alert) => (
              <div key={alert.id} className="alert-toast p-4">
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
  );
}
