'use client';

import { useEffect, useMemo, useState } from 'react';
import type { AlertItem, AlertStatus, WatchlistPerson } from '@/lib/types';
import { createWatchlistPerson, getAlerts, getWatchlistPersons } from '@/lib/api';
import { getUser } from '@/lib/auth';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select } from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { ErrorBanner } from '@/components/ui/error-banner';
import { WatchlistPersonsTable } from '@/components/tables/WatchlistPersonsTable';
import { formatUtc, humanAlertType } from '@/lib/formatters';

const tabs = ['persons', 'matches'] as const;
const MOCK_MODE = process.env.NEXT_PUBLIC_MOCK_MODE === 'true';
const mockPersons: WatchlistPerson[] = [
  {
    id: 'WL-001',
    name: 'R. Patel',
    alias: 'Gate Runner',
    reason: 'Theft',
    status: 'ACTIVE',
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    images: []
  }
];
const mockMatches: AlertItem[] = [
  {
    id: 'ALERT-001',
    godown_id: 'GDN_SAMPLE',
    godown_name: 'Pethapur',
    district: 'Gandhinagar',
    camera_id: 'CAM_GATE_1',
    alert_type: 'BLACKLIST_PERSON_MATCH',
    severity_final: 'critical',
    status: 'OPEN',
    start_time: new Date().toISOString(),
    summary: 'Blacklisted person detected',
    count_events: 1,
    key_meta: {
      person_name: 'R. Patel',
      match_score: 0.82,
      snapshot_url: '#'
    }
  }
];

type TabKey = (typeof tabs)[number];

export default function WatchlistPage() {
  const [activeTab, setActiveTab] = useState<TabKey>('persons');
  const [persons, setPersons] = useState<WatchlistPerson[]>([]);
  const [matches, setMatches] = useState<AlertItem[]>([]);
  const [status, setStatus] = useState('ACTIVE');
  const [search, setSearch] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({ name: '', alias: '', reason: '', notes: '' });
  const [files, setFiles] = useState<FileList | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [matchGodown, setMatchGodown] = useState('');
  const [minScore, setMinScore] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [dateNotice, setDateNotice] = useState<string | null>(null);

  useEffect(() => {
    if (!matchGodown) {
      const user = getUser();
      if (user?.godown_id) setMatchGodown(String(user.godown_id));
    }
  }, [matchGodown]);

  const matchParams = useMemo(() => ({
    alert_type: 'BLACKLIST_PERSON_MATCH',
    status: 'OPEN' as AlertStatus,
    page: 1,
    page_size: 50,
    godown_id: matchGodown || undefined,
    date_from: dateFrom ? new Date(dateFrom).toISOString() : undefined,
    date_to: dateTo ? new Date(dateTo).toISOString() : undefined
  }), [matchGodown, dateFrom, dateTo]);

  const filteredMatches = useMemo(() => {
    if (!minScore) return matches;
    const score = Number(minScore);
    if (Number.isNaN(score)) return matches;
    return matches.filter((m) => {
      const raw = m.key_meta?.match_score;
      if (raw === null || raw === undefined) return false;
      return Number(raw) >= score;
    });
  }, [matches, minScore]);

  useEffect(() => {
    let mounted = true;
    (async () => {
      setError(null);
      try {
        if (MOCK_MODE) {
          if (mounted) setPersons(mockPersons);
          return;
        }
        const resp = await getWatchlistPersons({ status, q: search || undefined, page: 1, page_size: 100 });
        if (mounted) setPersons(resp.items ?? []);
      } catch (e) {
        if (mounted) setError(e instanceof Error ? e.message : 'Failed to load watchlist');
      }
    })();
    return () => { mounted = false; };
  }, [status, search]);

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        if (MOCK_MODE) {
          if (mounted) setMatches(mockMatches);
          return;
        }
        const resp = await getAlerts(matchParams);
        const items = Array.isArray(resp) ? resp : resp.items ?? [];
        if (mounted) setMatches(items);
      } catch (e) {
        if (mounted) setError(e instanceof Error ? e.message : 'Failed to load matches');
      }
    })();
    return () => { mounted = false; };
  }, [matchParams]);

  async function submitNewPerson() {
    setError(null);
    if (!form.name.trim()) {
      setError('Name is required');
      return;
    }
    setIsSaving(true);
    try {
      const formData = new FormData();
      formData.append('name', form.name.trim());
      if (form.alias.trim()) formData.append('alias', form.alias.trim());
      if (form.reason.trim()) formData.append('reason', form.reason.trim());
      if (form.notes.trim()) formData.append('notes', form.notes.trim());
      if (files) {
        Array.from(files).forEach((file) => formData.append('reference_images', file));
      }
      await createWatchlistPerson(formData);
      setForm({ name: '', alias: '', reason: '', notes: '' });
      setFiles(null);
      const resp = await getWatchlistPersons({ status, q: search || undefined, page: 1, page_size: 100 });
      setPersons(resp.items ?? []);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to create watchlist person');
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="space-y-2">
          <div className="hud-pill">Blacklisted persons</div>
          <div className="text-4xl font-semibold font-display tracking-tight text-slate-100 drop-shadow">Watchlist Control</div>
          <div className="text-sm text-slate-300">Manage blacklisted persons and review recent matches.</div>
        </div>
        <div className="intel-banner">HQ only</div>
      </div>

      <div className="flex flex-wrap gap-2">
        {tabs.map((tab) => (
          <Button
            key={tab}
            variant={activeTab === tab ? 'default' : 'outline'}
            onClick={() => setActiveTab(tab)}
          >
            {tab === 'persons' ? 'Blacklisted Persons' : 'Recent Matches'}
          </Button>
        ))}
      </div>

      {error && <ErrorBanner message={error} onRetry={() => window.location.reload()} />}

      {activeTab === 'persons' && (
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
          <Card className="animate-fade-up hud-card">
            <CardHeader>
              <div className="text-lg font-semibold font-display">Add Blacklisted Person</div>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                <div>
                  <Label>Name</Label>
                  <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
                </div>
                <div>
                  <Label>Alias</Label>
                  <Input value={form.alias} onChange={(e) => setForm({ ...form, alias: e.target.value })} />
                </div>
                <div>
                  <Label>Reason</Label>
                  <Input value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} placeholder="Theft / fraud" />
                </div>
                <div>
                  <Label>Notes</Label>
                  <Input value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
                </div>
                <div>
                  <Label>Reference images</Label>
                  <Input type="file" multiple onChange={(e) => setFiles(e.target.files)} />
                </div>
                <Button onClick={submitNewPerson} disabled={isSaving}>{isSaving ? 'Saving...' : 'Add to Watchlist'}</Button>
              </div>
            </CardContent>
          </Card>

          <Card className="animate-fade-up hud-card xl:col-span-2">
            <CardHeader>
              <div className="text-lg font-semibold font-display">Watchlist directory</div>
              <div className="text-sm text-slate-300">Active blacklist across all godowns.</div>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
                <div>
                  <Label>Status</Label>
                  <Select
                    value={status}
                    onChange={(e) => setStatus(e.target.value)}
                    options={[
                      { label: 'Active', value: 'ACTIVE' },
                      { label: 'Inactive', value: 'INACTIVE' }
                    ]}
                  />
                </div>
                <div className="md:col-span-2">
                  <Label>Search by name</Label>
                  <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Name" />
                </div>
              </div>
              <WatchlistPersonsTable persons={persons} />
            </CardContent>
          </Card>
        </div>
      )}

      {activeTab === 'matches' && (
        <Card className="animate-fade-up hud-card">
          <CardHeader>
            <div className="text-lg font-semibold font-display">Recent blacklist alerts</div>
            <div className="text-sm text-slate-300">Latest matches across the network.</div>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-3 mb-4">
              <div>
                <Label>Godown</Label>
                <Input value={matchGodown} onChange={(e) => setMatchGodown(e.target.value)} placeholder="Auto (from login)" />
              </div>
              <div>
                <Label>Min score</Label>
                <Input value={minScore} onChange={(e) => setMinScore(e.target.value)} placeholder="0.75" />
              </div>
              <div>
                <Label>Date from</Label>
                <Input
                  type="date"
                  value={dateFrom}
                  max={dateTo || undefined}
                  onChange={(e) => {
                    const next = e.target.value;
                    setDateNotice(null);
                    setDateFrom(next);
                    if (next && dateTo && next > dateTo) {
                      setDateTo(next);
                      setDateNotice('Adjusted Date to to keep the range valid.');
                    }
                  }}
                />
              </div>
              <div>
                <Label>Date to</Label>
                <Input
                  type="date"
                  value={dateTo}
                  min={dateFrom || undefined}
                  onChange={(e) => {
                    const next = e.target.value;
                    setDateNotice(null);
                    setDateTo(next);
                    if (dateFrom && next && next < dateFrom) {
                      setDateFrom(next);
                      setDateNotice('Adjusted Date from to keep the range valid.');
                    }
                  }}
                />
              </div>
            </div>
            {dateNotice && <div className="text-xs text-amber-300 mb-4">{dateNotice}</div>}
            <div className="table-shell overflow-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="text-left text-slate-400">
                    <th className="py-2 pr-3">Time</th>
                    <th className="py-2 pr-3">Godown</th>
                    <th className="py-2 pr-3">Person</th>
                    <th className="py-2 pr-3">Score</th>
                    <th className="py-2 pr-3">Evidence</th>
                    <th className="py-2 pr-3">Alert</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredMatches.map((m) => (
                    <tr key={m.id} className="border-t border-white/10">
                      <td className="py-2 pr-3">{formatUtc(m.start_time)}</td>
                      <td className="py-2 pr-3">{m.godown_name ?? m.godown_id}</td>
                      <td className="py-2 pr-3">{m.key_meta?.person_name ?? m.key_meta?.person_id ?? '-'}</td>
                      <td className="py-2 pr-3">{m.key_meta?.match_score ?? '-'}</td>
                      <td className="py-2 pr-3">
                        {m.key_meta?.snapshot_url ? (
                          <a className="text-amber-300 hover:underline" href={String(m.key_meta.snapshot_url)} target="_blank" rel="noreferrer">
                            Snapshot
                          </a>
                        ) : (
                          '-'
                        )}
                      </td>
                      <td className="py-2 pr-3">{humanAlertType(m.alert_type)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}