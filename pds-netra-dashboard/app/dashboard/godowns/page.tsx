'use client';

import { useEffect, useMemo, useState } from 'react';
import { getGodowns } from '@/lib/api';
import type { GodownListItem } from '@/lib/types';
import { GodownsTable } from '@/components/tables/GodownsTable';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Select } from '@/components/ui/select';
import { ErrorBanner } from '@/components/ui/error-banner';

const statusOptions = [
  { label: 'All statuses', value: '' },
  { label: 'OK', value: 'OK' },
  { label: 'Issues', value: 'ISSUES' },
  { label: 'Critical', value: 'CRITICAL' }
];

export default function GodownsPage() {
  const [items, setItems] = useState<GodownListItem[]>([]);
  const [district, setDistrict] = useState('');
  const [status, setStatus] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const activeFilters = useMemo(() => {
    const chips: string[] = [];
    if (district.trim()) chips.push(`District: ${district.trim()}`);
    if (status) chips.push(`Status: ${status}`);
    return chips;
  }, [district, status]);

  useEffect(() => {
    let mounted = true;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await getGodowns({ district: district || undefined, status: status || undefined });
        if (mounted) setItems(data);
      } catch (e) {
        if (mounted) setError(e instanceof Error ? e.message : 'Failed to load godowns');
      } finally {
        if (mounted) setLoading(false);
      }
    })();
    return () => {
      mounted = false;
    };
  }, [district, status]);

  const districts = useMemo(() => {
    const unique = new Set(items.map((g) => g.district).filter(Boolean) as string[]);
    return Array.from(unique).sort();
  }, [items]);

  const districtOptions = useMemo(() => {
    return [{ label: 'All districts', value: '' }, ...districts.map((d) => ({ label: d, value: d }))];
  }, [districts]);

  return (
    <div className="space-y-4">
      <Card className="animate-fade-up">
        <CardHeader>
          <div className="text-xl font-semibold font-display">Godown Network</div>
          <div className="text-sm text-slate-600">Browse and filter monitored godowns</div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div>
              <div className="text-xs text-slate-600 mb-1">District</div>
              <Select value={district} onChange={(e) => setDistrict(e.target.value)} options={districtOptions} />
            </div>
            <div>
              <div className="text-xs text-slate-600 mb-1">Status</div>
              <Select value={status} onChange={(e) => setStatus(e.target.value)} options={statusOptions} />
            </div>
            <div className="flex items-end">
              <div className="text-xs text-slate-500">Tip: Click a godown to view camera health, alerts and events.</div>
            </div>
          </div>

          {activeFilters.length > 0 && (
            <div className="flex flex-wrap gap-2 mt-4">
              {activeFilters.map((chip) => (
                <span key={chip} className="badge-soft rounded-full px-3 py-1 text-[11px] uppercase tracking-[0.2em] text-slate-600">
                  {chip}
                </span>
              ))}
            </div>
          )}

          <div className="mt-4">
            {error && <ErrorBanner message={error} onRetry={() => window.location.reload()} />}
            {loading ? <div className="text-sm text-slate-600">Loading…</div> : <GodownsTable items={items} />}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
