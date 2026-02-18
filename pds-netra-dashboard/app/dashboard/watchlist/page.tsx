'use client';

import { useEffect, useMemo, useState } from 'react';
import type { AlertItem, AlertStatus, WatchlistPerson } from '@/lib/types';
import {
  addWatchlistImages,
  createWatchlistPerson,
  deleteBlacklistedPerson,
  getAlerts,
  getWatchlistPersons,
  updateBlacklistedPerson
} from '@/lib/api';
import { getUser } from '@/lib/auth';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select } from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { WatchlistPersonsTable } from '@/components/tables/WatchlistPersonsTable';
import { formatUtc, humanAlertType } from '@/lib/formatters';
import { friendlyErrorMessage } from '@/lib/friendly-error';
import { ToastStack, type ToastItem } from '@/components/ui/toast';
import {
  EditBlacklistedPersonSheet,
  type EditBlacklistedPersonPayload
} from '@/components/watchlist/EditBlacklistedPersonSheet';

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

function explainWatchlistUploadError(err: unknown, limitMb: string): string | null {
  if (err instanceof Error) {
    if (/413|Payload too large|Upload too large/i.test(err.message)) {
      return `Image exceeds ${limitMb} MB. Please choose a smaller file or compress and try again.`;
    }
  }
  return null;
}

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
  const [fileError, setFileError] = useState<string | null>(null);
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const [editTarget, setEditTarget] = useState<WatchlistPerson | null>(null);
  const [editOpen, setEditOpen] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);
  const [isEditSaving, setIsEditSaving] = useState(false);

  const [deleteBusyId, setDeleteBusyId] = useState<string | null>(null);

  const inlineErrorClass = 'text-xs text-red-400';
  const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;
  const maxUploadMb = (MAX_UPLOAD_BYTES / (1024 * 1024)).toFixed(1);

  function pushToast(toast: Omit<ToastItem, 'id'>) {
    const id = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    setToasts((items) => [...items, { id, ...toast }]);
  }

  useEffect(() => {
    if (!matchGodown) {
      const user = getUser();
      if (user?.godown_id) setMatchGodown(String(user.godown_id));
    }
  }, [matchGodown]);

  const matchParams = useMemo(
    () => ({
      alert_type: 'BLACKLIST_PERSON_MATCH',
      status: 'OPEN' as AlertStatus,
      page: 1,
      page_size: 50,
      godown_id: matchGodown || undefined,
      date_from: dateFrom ? new Date(dateFrom).toISOString() : undefined,
      date_to: dateTo ? new Date(dateTo).toISOString() : undefined
    }),
    [matchGodown, dateFrom, dateTo]
  );

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
        if (mounted)
          setError(friendlyErrorMessage(e, 'Unable to load the watchlist. Check your connection or try again.'));
      }
    })();
    return () => {
      mounted = false;
    };
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
        if (mounted)
          setError(friendlyErrorMessage(e, 'Unable to load match data. Please refresh or try again later.'));
      }
    })();
    return () => {
      mounted = false;
    };
  }, [matchParams]);

  async function reloadPersons() {
    const resp = await getWatchlistPersons({ status, q: search || undefined, page: 1, page_size: 100 });
    setPersons(resp.items ?? []);
  }

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
      await reloadPersons();
      pushToast({ type: 'success', title: 'Blacklisted person added', message: form.name.trim() });
    } catch (e) {
      const sizeMessage = explainWatchlistUploadError(e, maxUploadMb);
      if (sizeMessage) {
        setError(sizeMessage);
      } else {
        setError(friendlyErrorMessage(e, 'Unable to create a watchlist entry right now. Please try again.'));
      }
    } finally {
      setIsSaving(false);
    }
  }

  async function handleEditSave(payload: EditBlacklistedPersonPayload) {
    if (!editTarget) return;
    setEditError(null);
    if (!payload.name.trim()) {
      setEditError('Name is required.');
      return;
    }

    setIsEditSaving(true);
    try {
      await updateBlacklistedPerson(editTarget.id, {
        name: payload.name.trim(),
        alias: payload.alias.trim() || null,
        reason: payload.reason.trim() || null,
        notes: payload.notes.trim() || null,
        status: payload.status
      });

      if (payload.referenceImages && payload.referenceImages.length > 0) {
        const formData = new FormData();
        Array.from(payload.referenceImages).forEach((file) => formData.append('reference_images', file));
        await addWatchlistImages(editTarget.id, formData);
      }

      await reloadPersons();
      setEditOpen(false);
      setEditTarget(null);
      pushToast({ type: 'success', title: 'Blacklisted person updated', message: payload.name.trim() });
    } catch (e) {
      setEditError(friendlyErrorMessage(e, 'Unable to update this person. Please retry.'));
      pushToast({ type: 'error', title: 'Update failed', message: 'Could not save changes.' });
    } finally {
      setIsEditSaving(false);
    }
  }

  async function handleDeleteConfirm(target: WatchlistPerson) {
    setDeleteBusyId(target.id);
    try {
      await deleteBlacklistedPerson(target.id);
      await reloadPersons();
      pushToast({ type: 'success', title: 'Blacklisted person removed', message: target.name });
    } catch (e) {
      setError(friendlyErrorMessage(e, 'Unable to remove this person right now.'));
      pushToast({ type: 'error', title: 'Delete failed', message: 'Could not remove this person.' });
    } finally {
      setDeleteBusyId(null);
    }
  }

  return (
    <>
      <div className="space-y-5">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="space-y-2">
            <div className="hud-pill">Blacklisted persons</div>
            <div className="text-4xl font-semibold font-display tracking-tight text-slate-100 drop-shadow">
              Watchlist Control
            </div>
            <div className="text-sm text-slate-300">Manage blacklisted persons and review recent matches.</div>
          </div>
          <div className="intel-banner">HQ only</div>
        </div>

        <div className="flex flex-wrap gap-2">
          {tabs.map((tab) => (
            <Button key={tab} variant={activeTab === tab ? 'default' : 'outline'} onClick={() => setActiveTab(tab)}>
              {tab === 'persons' ? 'Blacklisted Persons' : 'Recent Matches'}
            </Button>
          ))}
        </div>

        {error && <p className={inlineErrorClass}>{error}</p>}

        {activeTab === 'persons' && (
          <div className="grid grid-cols-1 gap-4 xl:grid-cols-2 xl:items-start">
            <Card className="animate-fade-up hud-card">
              <CardHeader className="space-y-1">
                <div className="text-lg font-semibold font-display">Add Blacklisted Person</div>
                <p className="text-sm text-slate-300">Create a watchlist profile with optional reference photos.</p>
              </CardHeader>
              <Separator className="border-white/10" />
              <CardContent>
                <div className="space-y-4">
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
                    <Input
                      value={form.reason}
                      onChange={(e) => setForm({ ...form, reason: e.target.value })}
                      placeholder="Theft / fraud"
                    />
                  </div>
                  <div>
                    <Label>Notes</Label>
                    <Input value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
                  </div>
                  <div>
                    <Label>Reference images</Label>
                    <Input
                      type="file"
                      multiple
                      onChange={(e) => {
                        const selected = e.target.files;
                        if (!selected) {
                          setFiles(null);
                          setFileError(null);
                          return;
                        }
                        const oversized = Array.from(selected).find((file) => file.size > MAX_UPLOAD_BYTES);
                        if (oversized) {
                          setFiles(null);
                          setFileError(
                            `File too large (${(oversized.size / 1024 / 1024).toFixed(1)} MB). Max ${maxUploadMb} MB allowed.`
                          );
                          return;
                        }
                        setFiles(selected);
                        setFileError(null);
                      }}
                    />
                    {!fileError && <p className="mt-1 text-xs text-slate-400">Max image size: {maxUploadMb} MB</p>}
                    {fileError && <p className="mt-1 text-xs text-red-400">{fileError}</p>}
                  </div>
                  <Button onClick={submitNewPerson} disabled={isSaving} className="w-full">
                    {isSaving ? 'Saving...' : 'Add to Watchlist'}
                  </Button>
                </div>
              </CardContent>
            </Card>

            <Card className="animate-fade-up hud-card">
              <CardHeader>
                <div className="text-lg font-semibold font-display">Watchlist directory</div>
                <div className="text-sm text-slate-300">Active blacklist across all godowns.</div>
              </CardHeader>
              <Separator className="border-white/10" />
              <CardContent className="space-y-4">
                <div className="grid grid-cols-1 gap-3 md:grid-cols-[180px_minmax(0,1fr)]">
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
                  <div>
                    <Label>Search by name</Label>
                    <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Name" />
                  </div>
                </div>

                <WatchlistPersonsTable
                  persons={persons}
                  onEdit={(person) => {
                    setEditTarget(person);
                    setEditError(null);
                    setEditOpen(true);
                  }}
                  onDelete={(person) => void handleDeleteConfirm(person)}
                  deleteBusyId={deleteBusyId}
                />
                <div className="text-xs text-slate-500">
                  Showing {persons.length} person{persons.length !== 1 ? 's' : ''}
                </div>
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
                  <Input
                    value={matchGodown}
                    onChange={(e) => setMatchGodown(e.target.value)}
                    placeholder="Auto (from login)"
                  />
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
                <table className="min-w-[680px] text-sm">
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
                            <a
                              className="text-amber-300 hover:underline"
                              href={String(m.key_meta.snapshot_url)}
                              target="_blank"
                              rel="noreferrer"
                            >
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

      <EditBlacklistedPersonSheet
        open={editOpen}
        person={editTarget}
        isSaving={isEditSaving}
        error={editError}
        maxUploadMb={maxUploadMb}
        onOpenChange={(open) => {
          setEditOpen(open);
          if (!open) {
            setEditTarget(null);
            setEditError(null);
          }
        }}
        onSave={handleEditSave}
        onClearError={() => setEditError(null)}
      />

      <ToastStack items={toasts} onDismiss={(id) => setToasts((items) => items.filter((t) => t.id !== id))} />
    </>
  );
}
