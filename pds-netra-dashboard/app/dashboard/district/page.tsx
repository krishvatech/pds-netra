'use client';

import { useEffect, useMemo, useState } from 'react';
import { getAlerts, getGodowns } from '@/lib/api';
import type { AlertItem, GodownListItem } from '@/lib/types';
import { getUser } from '@/lib/auth';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Select } from '@/components/ui/select';
import { GodownsTable } from '@/components/tables/GodownsTable';
import { AlertsTable } from '@/components/tables/AlertsTable';
import { ErrorBanner } from '@/components/ui/error-banner';

export default function DistrictPage() {
  const [district, setDistrict] = useState('');
  const [godowns, setGodowns] = useState<GodownListItem[]>([]);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const user = getUser();
    if (user?.district) setDistrict(user.district);
  }, []);

  useEffect(() => {
    let mounted = true;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const godownResp = await getGodowns({ district: district || undefined });
        if (!mounted) return;
        const list = Array.isArray(godownResp) ? godownResp : godownResp.items;
        setGodowns(list);
        const alertResp = await getAlerts({ district: district || undefined, status: 'OPEN', page: 1, page_size: 20 });
        const items = Array.isArray(alertResp) ? alertResp : alertResp.items;
        setAlerts(items);
      } catch (e) {
        if (mounted) setError(e instanceof Error ? e.message : 'Failed to load district view');
      } finally {
        if (mounted) setLoading(false);
      }
    })();
    return () => {
      mounted = false;
    };
  }, [district]);

  const districts = useMemo(() => {
    const unique = new Set(godowns.map((g) => g.district).filter(Boolean) as string[]);
    return Array.from(unique).sort();
  }, [godowns]);

  const districtOptions = useMemo(() => {
    return [{ label: 'All districts', value: '' }, ...districts.map((d) => ({ label: d, value: d }))];
  }, [districts]);

  return (
    <div className="space-y-5">
      <div>
        <div className="text-3xl font-semibold font-display tracking-tight text-slate-100 drop-shadow">District Ops View</div>
        <div className="text-sm text-slate-300">Focused oversight for district operations.</div>
      </div>

      {error && (
        <Card>
          <CardContent>
            <ErrorBanner message={error} onRetry={() => window.location.reload()} />
          </CardContent>
        </Card>
      )}

      <Card className="animate-fade-up">
        <CardHeader>
          <div className="text-lg font-semibold font-display">Filters</div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div>
              <div className="text-xs text-slate-600 mb-1">District</div>
              <Select value={district} onChange={(e) => setDistrict(e.target.value)} options={districtOptions} />
            </div>
            <div className="flex items-end text-xs text-slate-500">Open alerts are scoped to the selected district.</div>
          </div>
        </CardContent>
      </Card>

      <Card className="animate-fade-up">
        <CardHeader>
          <div className="text-lg font-semibold font-display">Godowns in district</div>
        </CardHeader>
        <CardContent>
          {loading ? <div className="text-sm text-slate-600">Loading…</div> : <GodownsTable items={godowns} />}
        </CardContent>
      </Card>

      <Card className="animate-fade-up">
        <CardHeader>
          <div className="text-lg font-semibold font-display">Open alerts</div>
        </CardHeader>
        <CardContent>
          {loading ? <div className="text-sm text-slate-600">Loading…</div> : <AlertsTable alerts={alerts} />}
        </CardContent>
      </Card>
    </div>
  );
}