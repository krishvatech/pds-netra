'use client';

import { useMemo, useState, useEffect, Fragment } from 'react';
import { exportAlertsCsvUrl, exportMovementCsvUrl, generateHqReport, getHqReportDeliveries, getHqReports } from '@/lib/api';
import type { AlertDelivery, AlertReport } from '@/lib/types';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { ErrorBanner } from '@/components/ui/error-banner';
import { formatUtc } from '@/lib/formatters';

function isoDate(value: string) {
  if (!value) return '';
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return '';
  return dt.toISOString();
}

export default function ReportsPage() {
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [godownId, setGodownId] = useState('');
  const [hqReports, setHqReports] = useState<AlertReport[]>([]);
  const [deliveries, setDeliveries] = useState<Record<string, AlertDelivery[]>>({});
  const [hqError, setHqError] = useState<string | null>(null);
  const [hqLoading, setHqLoading] = useState(false);
  const [hqGenerating, setHqGenerating] = useState(false);

  const urls = useMemo(() => {
    const params = {
      godown_id: godownId || undefined,
      date_from: from ? isoDate(from) : undefined,
      date_to: to ? isoDate(to) : undefined
    };
    return {
      alerts: exportAlertsCsvUrl(params),
      movement: exportMovementCsvUrl(params)
    };
  }, [from, to, godownId]);

  async function loadHqReports() {
    setHqError(null);
    setHqLoading(true);
    try {
      const rows = await getHqReports(30);
      setHqReports(rows ?? []);
    } catch (e) {
      setHqError(e instanceof Error ? e.message : 'Failed to load HQ reports');
    } finally {
      setHqLoading(false);
    }
  }

  useEffect(() => {
    loadHqReports();
  }, []);

  async function triggerReport(period: '24h' | '1h') {
    setHqError(null);
    setHqGenerating(true);
    try {
      await generateHqReport(period);
      await loadHqReports();
    } catch (e) {
      setHqError(e instanceof Error ? e.message : 'Failed to generate HQ report');
    } finally {
      setHqGenerating(false);
    }
  }

  async function toggleDeliveries(reportId: string) {
    if (deliveries[reportId]) {
      const next = { ...deliveries };
      delete next[reportId];
      setDeliveries(next);
      return;
    }
    try {
      const rows = await getHqReportDeliveries(reportId);
      setDeliveries((prev) => ({ ...prev, [reportId]: rows ?? [] }));
    } catch (e) {
      setHqError(e instanceof Error ? e.message : 'Failed to load delivery status');
    }
  }

  return (
    <div className="space-y-5">
      <div>
        <div className="text-3xl font-semibold font-display tracking-tight text-slate-100 drop-shadow">Reports & Exports</div>
        <div className="text-sm text-slate-300">Download compliance and operations data for audits.</div>
      </div>

      <Card className="animate-fade-up">
        <CardHeader>
          <div className="text-lg font-semibold font-display">Export filters</div>
          <div className="text-sm text-slate-600">Optional filters apply to both alert and movement exports.</div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div>
              <div className="text-xs text-slate-600 mb-1">From date</div>
              <Input type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
            </div>
            <div>
              <div className="text-xs text-slate-600 mb-1">To date</div>
              <Input type="date" value={to} onChange={(e) => setTo(e.target.value)} />
            </div>
            <div>
              <div className="text-xs text-slate-600 mb-1">Godown ID (optional)</div>
              <Input value={godownId} onChange={(e) => setGodownId(e.target.value)} placeholder="GDN_001" />
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card className="animate-fade-up report-tile">
          <CardHeader>
            <div className="text-lg font-semibold font-display">Alert export</div>
            <div className="text-sm text-slate-600">All alert records with status and severity.</div>
          </CardHeader>
          <CardContent>
            <Button onClick={() => window.open(urls.alerts, '_blank')}>Download CSV</Button>
          </CardContent>
        </Card>
        <Card className="animate-fade-up report-tile">
          <CardHeader>
            <div className="text-lg font-semibold font-display">Movement export</div>
            <div className="text-sm text-slate-600">Foodgrain movement events with plan IDs.</div>
          </CardHeader>
          <CardContent>
            <Button onClick={() => window.open(urls.movement, '_blank')}>Download CSV</Button>
          </CardContent>
        </Card>
      </div>

      <Card className="animate-fade-up hud-card">
        <CardHeader>
          <div className="text-lg font-semibold font-display">HQ Alert Reports</div>
          <div className="text-sm text-slate-600">Digest reports sent to HQ only.</div>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2 mb-4">
            <Button onClick={() => triggerReport('24h')} disabled={hqGenerating}>
              {hqGenerating ? 'Generating...' : 'Generate daily report'}
            </Button>
            <Button variant="outline" onClick={() => triggerReport('1h')} disabled={hqGenerating}>
              Generate hourly report
            </Button>
            <Button variant="outline" onClick={loadHqReports} disabled={hqLoading}>
              Refresh list
            </Button>
          </div>

          {hqError && <ErrorBanner message={hqError} onRetry={loadHqReports} />}

          {hqLoading ? (
            <div className="text-sm text-slate-600">Loading reports...</div>
          ) : (
            <div className="table-shell overflow-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="text-left text-slate-400">
                    <th className="py-2 pr-3">Generated</th>
                    <th className="py-2 pr-3">Period</th>
                    <th className="py-2 pr-3">Total alerts</th>
                    <th className="py-2 pr-3">Critical open</th>
                    <th className="py-2 pr-3">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {hqReports.map((r) => (
                    <Fragment key={r.id}>
                      <tr className="border-t border-white/10">
                        <td className="py-2 pr-3">{formatUtc(r.generated_at)}</td>
                        <td className="py-2 pr-3">
                          {formatUtc(r.period_start)} → {formatUtc(r.period_end)}
                        </td>
                        <td className="py-2 pr-3">{r.summary_json?.total_alerts ?? '-'}</td>
                        <td className="py-2 pr-3">{r.summary_json?.open_critical_alerts ?? '-'}</td>
                        <td className="py-2 pr-3">
                          <Button variant="outline" onClick={() => toggleDeliveries(r.id)}>
                            {deliveries[r.id] ? 'Hide deliveries' : 'View deliveries'}
                          </Button>
                        </td>
                      </tr>
                      {deliveries[r.id] && (
                        <tr className="border-t border-white/10">
                          <td colSpan={5} className="py-3">
                            {deliveries[r.id].length === 0 ? (
                              <div className="text-sm text-slate-500">No delivery records.</div>
                            ) : (
                              <div className="table-shell overflow-auto">
                                <table className="min-w-full text-sm">
                                  <thead>
                                    <tr className="text-left text-slate-400">
                                      <th className="py-2 pr-3">Channel</th>
                                      <th className="py-2 pr-3">Target</th>
                                      <th className="py-2 pr-3">Status</th>
                                      <th className="py-2 pr-3">Attempts</th>
                                      <th className="py-2 pr-3">Sent at</th>
                                      <th className="py-2 pr-3">Last error</th>
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {deliveries[r.id].map((d) => (
                                      <tr key={d.id} className="border-t border-white/10">
                                        <td className="py-2 pr-3">{d.channel}</td>
                                        <td className="py-2 pr-3">{d.target}</td>
                                        <td className="py-2 pr-3">{d.status}</td>
                                        <td className="py-2 pr-3">{d.attempts}</td>
                                        <td className="py-2 pr-3">{formatUtc(d.sent_at ?? null)}</td>
                                        <td className="py-2 pr-3 text-xs text-slate-400">{d.last_error ?? '-'}</td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </div>
                            )}
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  ))}
                  {hqReports.length === 0 && (
                    <tr>
                      <td colSpan={5} className="py-6 text-center text-slate-500">No HQ reports generated yet.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
