'use client';

import { useMemo, useState } from 'react';
import { exportAlertsCsvUrl, exportMovementCsvUrl } from '@/lib/api';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';

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
    </div>
  );
}
