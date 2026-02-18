'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { getUser } from '@/lib/auth';
import {
  createAnprVehicle,
  getAnprVehicles,
  updateAnprVehicle,
  deleteAnprVehicle,
  getGodowns,
  importAnprVehiclesCsv
} from '@/lib/api';
import type { AnprVehicle, GodownListItem, CsvImportSummary } from '@/lib/types';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Table, THead, TBody, TR, TH, TD } from '@/components/ui/table';
import { ErrorBanner } from '@/components/ui/error-banner';

type CsvPreviewRow = {
  plate_text: string;
  list_type?: string;
  transporter?: string;
  notes?: string;
  is_active?: string;
  error?: string;
};

function parseCsvLine(line: string): string[] {
  const out: string[] = [];
  let cur = '';
  let inQuotes = false;
  for (let i = 0; i < line.length; i += 1) {
    const ch = line[i];
    if (ch === '"') {
      if (inQuotes && line[i + 1] === '"') {
        cur += '"';
        i += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }
    if (ch === ',' && !inQuotes) {
      out.push(cur);
      cur = '';
      continue;
    }
    cur += ch;
  }
  out.push(cur);
  return out;
}

function parseCsv(text: string): CsvPreviewRow[] {
  const lines = text.split(/\r?\n/).filter((l) => l.trim() !== '');
  if (lines.length === 0) return [];
  const header = parseCsvLine(lines[0]).map((h) => h.trim().toLowerCase());
  const rows: CsvPreviewRow[] = [];
  for (let i = 1; i < lines.length; i += 1) {
    const values = parseCsvLine(lines[i]);
    const row: Record<string, string> = {};
    header.forEach((key, idx) => {
      row[key] = (values[idx] ?? '').trim();
    });
    const plate_text =
      row['plate_text'] || row['plate'] || row['plate_no'] || row['plate_number'] || '';
    const preview: CsvPreviewRow = {
      plate_text,
      list_type: row['list_type'] || '',
      transporter: row['transporter'] || '',
      notes: row['notes'] || '',
      is_active: row['is_active'] || ''
    };
    if (!plate_text.trim()) {
      preview.error = 'plate_text required';
    }
    rows.push(preview);
  }
  return rows;
}

function toCsvValue(value: string) {
  if (value.includes('"') || value.includes(',') || value.includes('\n')) {
    return `"${value.replace(/"/g, '""')}"`;
  }
  return value;
}

function buildCsv(rows: CsvPreviewRow[]): string {
  const header = ['plate_text', 'list_type', 'transporter', 'notes', 'is_active'];
  const lines = [header.join(',')];
  for (const row of rows) {
    const line = [
      row.plate_text || '',
      row.list_type || '',
      row.transporter || '',
      row.notes || '',
      row.is_active || ''
    ].map(toCsvValue);
    lines.push(line.join(','));
  }
  return lines.join('\n');
}

export default function AnprVehiclesPage() {
  const [godownId, setGodownId] = useState('');
  const [godowns, setGodowns] = useState<GodownListItem[]>([]);
  const [q, setQ] = useState('');
  const [activeOnly, setActiveOnly] = useState(false);

  const [plateText, setPlateText] = useState('');
  const [listType, setListType] = useState<'WHITELIST' | 'BLACKLIST'>('WHITELIST');
  const [transporter, setTransporter] = useState('');
  const [notes, setNotes] = useState('');

  const [items, setItems] = useState<AnprVehicle[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [importFile, setImportFile] = useState<File | null>(null);
  const [importRows, setImportRows] = useState<CsvPreviewRow[]>([]);
  const [importError, setImportError] = useState<string | null>(null);
  const [importResult, setImportResult] = useState<CsvImportSummary | null>(null);
  const [importBusy, setImportBusy] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const registryRef = useRef<HTMLDivElement | null>(null);

  // IMPORTANT: keep as string, but always store String(v.id)
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);
  const [editId, setEditId] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState<{
    plate_text: string;
    list_type: 'WHITELIST' | 'BLACKLIST';
    transporter: string;
    notes: string;
    is_active: boolean;
  } | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<AnprVehicle | null>(null);

  // Import preview row menu (still uses "...", separate from main table)
  const [importMenuId, setImportMenuId] = useState<number | null>(null);
  const [editRowIndex, setEditRowIndex] = useState<number | null>(null);
  const [editRowDraft, setEditRowDraft] = useState<CsvPreviewRow | null>(null);

  const godownOptions = useMemo(() => {
    const opts = godowns.map((g) => ({ label: g.name || g.godown_id, value: g.godown_id }));
    if (godownId && !opts.some((o) => o.value === godownId)) {
      return [{ label: godownId, value: godownId }, ...opts];
    }
    return opts;
  }, [godowns, godownId]);

  useEffect(() => {
    if (!godownId) {
      const user = getUser();
      if (user?.godown_id) setGodownId(String(user.godown_id));
    }
  }, [godownId]);

  useEffect(() => {
    let alive = true;
    async function loadGodowns() {
      try {
        const resp = await getGodowns({});
        const list = Array.isArray(resp) ? resp : resp.items;
        if (alive) setGodowns(list || []);
      } catch {
        // ignore
      }
    }
    loadGodowns();
    return () => {
      alive = false;
    };
  }, []);

  async function load() {
    if (!godownId) return;
    try {
      setError(null);
      const resp = await getAnprVehicles({
        godown_id: godownId,
        q: q || undefined,
        is_active: activeOnly ? true : undefined,
        page: 1,
        page_size: 200
      });
      setItems(resp.items || []);
    } catch (e: any) {
      setError(e?.message || 'Failed to load vehicles');
    }
  }

  useEffect(() => {
    const t = setInterval(load, 5000);
    load();
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [godownId, q, activeOnly]);

  // Close row menu when clicking outside
  useEffect(() => {
    if (!openMenuId) return;
    const onClick = () => setOpenMenuId(null);
    document.addEventListener('click', onClick);
    return () => document.removeEventListener('click', onClick);
  }, [openMenuId]);

  useEffect(() => {
    if (importMenuId === null) return;
    const onClick = () => setImportMenuId(null);
    document.addEventListener('click', onClick);
    return () => document.removeEventListener('click', onClick);
  }, [importMenuId]);

  function openEditRow(idx: number) {
    const row = importRows[idx];
    if (!row) return;
    setEditRowIndex(idx);
    setEditRowDraft({ ...row });
  }

  function applyEditRow() {
    if (editRowIndex === null || !editRowDraft) return;
    const next = [...importRows];
    const updated = { ...editRowDraft };
    updated.error = updated.plate_text.trim() ? undefined : 'plate_text required';
    next[editRowIndex] = updated;
    setImportRows(next);
    setEditRowIndex(null);
    setEditRowDraft(null);
  }

  function deleteRow(idx: number) {
    const next = importRows.filter((_, i) => i !== idx);
    setImportRows(next);
  }

  const stats = useMemo(() => {
    const total = items.length;
    const active = items.filter((v) => v.is_active).length;
    return { total, active };
  }, [items]);

  async function onCreate() {
    if (!godownId) return;
    const plate = plateText.trim();
    if (!plate) return;
    try {
      setBusy(true);
      setError(null);
      await createAnprVehicle({
        godown_id: godownId,
        plate_text: plate,
        list_type: listType,
        transporter: transporter.trim() || null,
        notes: notes.trim() || null,
        is_active: true
      });
      setPlateText('');
      setListType('WHITELIST');
      setTransporter('');
      setNotes('');
      await load();
    } catch (e: any) {
      setError(e?.message || 'Failed to create vehicle');
    } finally {
      setBusy(false);
    }
  }

  async function onToggleActive(v: AnprVehicle) {
    try {
      setBusy(true);
      setError(null);
      await updateAnprVehicle(v.id, { is_active: !v.is_active });
      await load();
    } catch (e: any) {
      setError(e?.message || 'Failed to update vehicle');
    } finally {
      setBusy(false);
    }
  }

  async function onQuickEdit(v: AnprVehicle) {
    setEditId(String(v.id));
    setEditDraft({
      plate_text: v.plate_raw || '',
      list_type: ((v.list_type || 'WHITELIST').toUpperCase() as 'WHITELIST' | 'BLACKLIST') || 'WHITELIST',
      transporter: v.transporter || '',
      notes: v.notes || '',
      is_active: !!v.is_active
    });
  }

  function cancelInlineEdit() {
    setEditId(null);
    setEditDraft(null);
  }

  async function saveInlineEdit(v: AnprVehicle) {
    if (!editDraft) return;
    const plate = editDraft.plate_text.trim();
    if (!plate) {
      setError('Plate is required');
      return;
    }
    try {
      setBusy(true);
      setError(null);
      await updateAnprVehicle(v.id, {
        plate_text: plate,
        list_type: editDraft.list_type,
        transporter: editDraft.transporter.trim() ? editDraft.transporter.trim() : null,
        notes: editDraft.notes.trim() ? editDraft.notes.trim() : null,
        is_active: editDraft.is_active
      });
      cancelInlineEdit();
      await load();
    } catch (e: any) {
      setError(e?.message || 'Failed to update vehicle');
    } finally {
      setBusy(false);
    }
  }

  async function onDelete(v: AnprVehicle) {
    try {
      setBusy(true);
      setError(null);
      await deleteAnprVehicle(v.id);
      await load();
    } catch (e: any) {
      setError(e?.message || 'Failed to delete vehicle');
    } finally {
      setBusy(false);
    }
  }

  async function onImportFileChange(file: File | null) {
    setImportResult(null);
    setImportError(null);
    setImportRows([]);
    setImportFile(file);
    if (!file) return;
    try {
      const text = await file.text();
      setImportRows(parseCsv(text));
    } catch (e: any) {
      setImportError(e?.message || 'Failed to read CSV file');
    }
  }

  async function onImportCsv() {
    if (!importFile || !godownId) return;
    try {
      setImportBusy(true);
      setImportError(null);
      const rowsToSend = importRows.length ? importRows : [];
      const csvText = rowsToSend.length ? buildCsv(rowsToSend) : '';
      const fileToSend =
        rowsToSend.length
          ? new File([csvText], importFile.name || 'vehicle_registry_import.csv', { type: 'text/csv' })
          : importFile;

      const resp = await importAnprVehiclesCsv({ godown_id: godownId, file: fileToSend });
      setImportResult(resp);
      await load();
      setImportOpen(false);
      setTimeout(() => {
        registryRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 50);
    } catch (e: any) {
      setImportError(e?.message || 'Failed to import CSV');
    } finally {
      setImportBusy(false);
    }
  }

  return (
    <>
      <div className="space-y-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="space-y-2">
            <div className="hud-pill">ANPR Registry</div>
            <div className="text-4xl font-semibold font-display tracking-tight text-slate-100 drop-shadow">
              Vehicle Registry
            </div>
            <div className="text-sm text-slate-300">
              Maintain lists, import CSVs, and manage plate status per godown.
            </div>
          </div>
          <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3 w-full lg:w-auto">
            <div className="hud-card w-full p-4 sm:min-w-[220px]">
              <div className="hud-label">Active / Total</div>
              <div className="hud-value">
                {stats.active} / {stats.total}
              </div>
              <div className="text-xs text-slate-500">
                Scope: {godownId ? godownId : 'Select godown'}
              </div>
            </div>
            <Button
              className="w-full sm:w-auto rounded-full px-4 py-2 text-xs uppercase tracking-[0.2em] bg-blue-600 hover:bg-blue-700 text-white"
              onClick={() => setImportOpen(true)}
            >
              Import CSV
            </Button>
          </div>
        </div>

        {error && <ErrorBanner message={error} />}

        {importOpen && (
          <Card className="hud-card">
            <CardHeader className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div>
                <div className="text-xl font-semibold font-display text-white">Import Vehicles (CSV)</div>
                <div className="text-xs text-slate-400">Bulk load plates into the registry.</div>
              </div>
              <Button variant="outline" className="w-full md:w-auto" onClick={() => setImportOpen(false)}>
                Close
              </Button>
            </CardHeader>
            <CardContent className="space-y-4">
              {importError && <ErrorBanner message={importError} />}

              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                <div>
                  <Label>CSV File</Label>
                  <Input
                    type="file"
                    accept=".csv,text/csv"
                    onChange={(e) => onImportFileChange(e.target.files?.[0] || null)}
                  />
                </div>
                <div>
                  <Label>Godown</Label>
                  <Select
                    value={godownId}
                    onChange={(e) => setGodownId(e.target.value)}
                    options={godownOptions}
                    placeholder="Select godown..."
                  />
                </div>
              </div>

              <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                <div className="text-xs text-slate-400">
                  Columns: plate_text, list_type, transporter, notes, is_active
                </div>
                <Button className="w-full md:w-auto" onClick={onImportCsv} disabled={importBusy || !importFile || !godownId}>
                  {importBusy ? 'Importing...' : 'Import CSV'}
                </Button>
              </div>

              {importRows.length > 0 && (
                <div className="space-y-2">
                  <div className="text-xs text-slate-300">
                    Preview rows: {importRows.length} (errors: {importRows.filter((r) => r.error).length})
                  </div>

                  <div className="table-shell overflow-auto">
                    <Table>
                      <THead>
                        <TR>
                          <TH>Plate</TH>
                          <TH>List</TH>
                          <TH>Transporter</TH>
                          <TH>Notes</TH>
                          <TH>Active</TH>
                          <TH>Issue</TH>
                          <TH>Actions</TH>
                        </TR>
                      </THead>
                      <TBody>
                        {importRows.map((r, idx) => (
                          <TR key={`${r.plate_text}-${idx}`}>
                            <TD className="font-semibold min-w-[160px]">{r.plate_text || 'N/A'}</TD>
                            <TD className="min-w-[140px]">{r.list_type || 'N/A'}</TD>
                            <TD className="min-w-[180px]">{r.transporter || 'N/A'}</TD>
                            <TD className="min-w-[220px]">{r.notes || 'N/A'}</TD>
                            <TD className="min-w-[120px]">{r.is_active || 'N/A'}</TD>
                            <TD className="text-xs text-amber-300">{r.error || 'N/A'}</TD>
                            <TD className="w-[70px]">
                              <div className="relative inline-flex">
                                <button
                                  type="button"
                                  className="rounded-md border border-white/10 bg-white/5 px-2 py-1 text-xs text-slate-100 hover:bg-white/10"
                                  aria-label="Open row actions"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setImportMenuId((prev) => (prev === idx ? null : idx));
                                  }}
                                >
                                  ...
                                </button>
                                {importMenuId === idx && (
                                  <div
                                    className="absolute right-0 z-20 mt-2 w-32 rounded-lg border border-white/10 bg-slate-950/95 p-1 shadow-xl"
                                    onClick={(e) => e.stopPropagation()}
                                  >
                                    <button
                                      type="button"
                                      className="block w-full rounded-md px-3 py-2 text-left text-xs text-slate-200 hover:bg-white/10"
                                      onClick={() => {
                                        setImportMenuId(null);
                                        openEditRow(idx);
                                      }}
                                    >
                                      Edit
                                    </button>
                                    <button
                                      type="button"
                                      className="block w-full rounded-md px-3 py-2 text-left text-xs text-rose-300 hover:bg-rose-500/20"
                                      onClick={() => {
                                        setImportMenuId(null);
                                        deleteRow(idx);
                                      }}
                                    >
                                      Delete
                                    </button>
                                  </div>
                                )}
                              </div>
                            </TD>
                          </TR>
                        ))}
                      </TBody>
                    </Table>
                  </div>
                </div>
              )}

              {importResult && (
                <div className="text-xs text-slate-300">
                  Imported: {importResult.total} | Created: {importResult.created} | Updated: {importResult.updated} |
                  Failed: {importResult.failed}
                </div>
              )}
            </CardContent>
          </Card>
        )}

        <div className="grid grid-cols-1 gap-4">
          <Card className="hud-card">
            <CardHeader className="flex items-center justify-between">
              <div className="text-lg font-semibold font-display">Add Vehicle</div>
              <div className="hud-pill">Manual entry</div>
            </CardHeader>
            <CardContent className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <div className="md:col-span-2">
                <Label>Godown</Label>
                <Select
                  value={godownId}
                  onChange={(e) => setGodownId(e.target.value)}
                  options={godownOptions}
                  placeholder="Select godown..."
                />
              </div>

              <div>
                <Label>Plate</Label>
                <Input
                  value={plateText}
                  onChange={(e) => setPlateText(e.target.value)}
                  placeholder="e.g. WB23D5690"
                />
              </div>

              <div>
                <Label>List Type</Label>
                <Select
                  value={listType}
                  onChange={(e) => setListType(e.target.value as 'WHITELIST' | 'BLACKLIST')}
                  options={[
                    { label: 'WHITELIST', value: 'WHITELIST' },
                    { label: 'BLACKLIST', value: 'BLACKLIST' }
                  ]}
                />
              </div>

              <div>
                <Label>Transporter</Label>
                <Input
                  value={transporter}
                  onChange={(e) => setTransporter(e.target.value)}
                  placeholder="optional"
                />
              </div>

              <div>
                <Label>Notes</Label>
                <Input value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="optional" />
              </div>

              <div className="md:col-span-2 flex flex-wrap items-center gap-2">
                <Button onClick={onCreate} disabled={busy || !godownId || !plateText.trim()}>
                  Add Vehicle
                </Button>
                <div className="text-xs text-slate-400">
                  Status: {stats.active} active | {stats.total} total
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        <Card className="hud-card" ref={registryRef}>
          <CardHeader className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
            <div className="text-lg font-semibold font-display">Vehicle Registry</div>
            <div className="hud-pill">Live refresh 5s</div>
          </CardHeader>

          <CardContent className="space-y-3">
            <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
              <div>
                <Label>Search</Label>
                <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="plate contains..." />
              </div>
              <div>
                <Label>Active Only</Label>
                <select
                  className="w-full rounded-xl px-3 py-2 text-sm border border-white/10 bg-white/5"
                  value={activeOnly ? '1' : '0'}
                  onChange={(e) => setActiveOnly(e.target.value === '1')}
                >
                  <option value="0">All</option>
                  <option value="1">Active</option>
                </select>
              </div>
            </div>

            <div className="table-shell overflow-auto">
              <Table>
                <THead>
                  <TR>
                    <TH>Plate</TH>
                    <TH>List</TH>
                    <TH>Status</TH>
                    <TH>Transporter</TH>
                    <TH>Notes</TH>
                    <TH className="text-right">Actions</TH>
                  </TR>
                </THead>

                <TBody>
                  {items.length === 0 ? (
                    <TR>
                      <TD colSpan={6} className="text-sm text-slate-500">
                        No vehicles
                      </TD>
                    </TR>
                  ) : (
                    items.map((v) => (
                      <TR key={v.id}>
                        <TD className="font-semibold">
                          {editId === String(v.id) && editDraft ? (
                            <Input
                              value={editDraft.plate_text}
                              onChange={(e) => setEditDraft({ ...editDraft, plate_text: e.target.value })}
                              placeholder="plate"
                            />
                          ) : (
                            v.plate_raw
                          )}
                        </TD>
                        <TD>
                          {editId === String(v.id) && editDraft ? (
                            <Select
                              value={editDraft.list_type}
                              onChange={(e) =>
                                setEditDraft({ ...editDraft, list_type: e.target.value as 'WHITELIST' | 'BLACKLIST' })
                              }
                              options={[
                                { label: 'WHITELIST', value: 'WHITELIST' },
                                { label: 'BLACKLIST', value: 'BLACKLIST' }
                              ]}
                            />
                          ) : (
                            <Badge
                              className={
                                (v.list_type || 'WHITELIST').toUpperCase() === 'BLACKLIST'
                                  ? 'bg-red-100 text-red-800 border border-red-200'
                                  : 'bg-blue-100 text-blue-800 border border-blue-200'
                              }
                            >
                              {(v.list_type || 'WHITELIST').toUpperCase()}
                            </Badge>
                          )}
                        </TD>

                        <TD>
                          {editId === String(v.id) && editDraft ? (
                            <Select
                              value={editDraft.is_active ? '1' : '0'}
                              onChange={(e) => setEditDraft({ ...editDraft, is_active: e.target.value === '1' })}
                              options={[
                                { label: 'ACTIVE', value: '1' },
                                { label: 'INACTIVE', value: '0' }
                              ]}
                            />
                          ) : v.is_active ? (
                            <Badge className="bg-green-100 text-green-800 border border-green-200">ACTIVE</Badge>
                          ) : (
                            <Badge className="bg-slate-100 text-slate-700 border border-slate-200">INACTIVE</Badge>
                          )}
                        </TD>

                        <TD>
                          {editId === String(v.id) && editDraft ? (
                            <Input
                              value={editDraft.transporter}
                              onChange={(e) => setEditDraft({ ...editDraft, transporter: e.target.value })}
                              placeholder="transporter"
                            />
                          ) : (
                            v.transporter || 'N/A'
                          )}
                        </TD>
                        <TD className="max-w-[360px] truncate">
                          {editId === String(v.id) && editDraft ? (
                            <Input
                              value={editDraft.notes}
                              onChange={(e) => setEditDraft({ ...editDraft, notes: e.target.value })}
                              placeholder="notes"
                            />
                          ) : (
                            v.notes || 'N/A'
                          )}
                        </TD>

                        {/* ✅ FIXED ACTIONS COLUMN (Toggle + visible 3-dot + working dropdown) */}
                        <TD>
                          <div className="flex flex-wrap items-center justify-start gap-2 md:justify-end">
                            {editId === String(v.id) ? (
                              <>
                                <Button
                                  className="px-3 py-1.5 text-xs"
                                  onClick={() => saveInlineEdit(v)}
                                  disabled={busy}
                                >
                                  Save
                                </Button>
                                <Button
                                  variant="outline"
                                  className="px-3 py-1.5 text-xs"
                                  onClick={cancelInlineEdit}
                                  disabled={busy}
                                >
                                  Cancel
                                </Button>
                              </>
                            ) : (
                              <Button
                                variant="outline"
                                className="px-3 py-1.5 text-xs"
                                onClick={() => onToggleActive(v)}
                                disabled={busy}
                              >
                                {v.is_active ? 'Deactivate' : 'Activate'}
                              </Button>
                            )}

                            <div className="relative">
                              <button
                                type="button"
                                className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-900 hover:bg-slate-50"
                                aria-label="More actions"
                                disabled={editId === String(v.id)}
                                onClick={(e) => {
                                  e.stopPropagation();
                                  const id = String(v.id);
                                  setOpenMenuId((prev) => (prev === id ? null : id));
                                }}
                              >
                                <span className="text-xl leading-none">⋮</span>
                              </button>

                              {openMenuId === String(v.id) && (
                                <div
                                  className="absolute right-0 z-50 mt-2 w-36 rounded-lg border border-slate-200 bg-white p-1 shadow-lg"
                                  onClick={(e) => e.stopPropagation()}
                                >
                                  <button
                                    type="button"
                                    className="block w-full rounded-md px-3 py-2 text-left text-sm text-slate-900 hover:bg-slate-100"
                                    onClick={() => {
                                      setOpenMenuId(null);
                                      onQuickEdit(v);
                                    }}
                                  >
                                    Edit
                                  </button>

                                  <button
                                    type="button"
                                    className="block w-full rounded-md px-3 py-2 text-left text-sm text-rose-700 hover:bg-rose-50"
                                    onClick={() => {
                                      setOpenMenuId(null);
                                      setDeleteTarget(v);
                                    }}
                                  >
                                    Delete
                                  </button>
                                </div>
                              )}
                            </div>
                          </div>
                        </TD>
                      </TR>
                    ))
                  )}
                </TBody>
              </Table>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* IMPORT ROW EDIT MODAL (unchanged) */}
      {editRowDraft && editRowIndex !== null && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
          <button
            className="absolute inset-0 bg-slate-950/70 backdrop-blur-sm"
            onClick={() => {
              setEditRowIndex(null);
              setEditRowDraft(null);
            }}
            aria-label="Close edit"
          />
          <div
            className="modal-shell modal-body relative w-full rounded-2xl border border-white/10 bg-slate-950/95 p-6 shadow-2xl"
            role="dialog"
            aria-modal="true"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="text-lg font-semibold font-display text-white">Edit CSV Row</div>
            <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
              <div className="md:col-span-2">
                <Label>Plate</Label>
                <Input
                  value={editRowDraft.plate_text}
                  onChange={(e) => setEditRowDraft({ ...editRowDraft, plate_text: e.target.value })}
                  placeholder="plate_text"
                />
              </div>
              <div>
                <Label>List Type</Label>
                <Select
                  value={(editRowDraft.list_type || 'WHITELIST').toUpperCase()}
                  onChange={(e) => setEditRowDraft({ ...editRowDraft, list_type: e.target.value })}
                  options={[
                    { label: 'WHITELIST', value: 'WHITELIST' },
                    { label: 'BLACKLIST', value: 'BLACKLIST' }
                  ]}
                />
              </div>
              <div>
                <Label>Active</Label>
                <Select
                  value={(editRowDraft.is_active || '').toUpperCase()}
                  onChange={(e) => setEditRowDraft({ ...editRowDraft, is_active: e.target.value })}
                  options={[
                    { label: 'TRUE', value: 'true' },
                    { label: 'FALSE', value: 'false' },
                    { label: 'N/A', value: '' }
                  ]}
                />
              </div>
              <div>
                <Label>Transporter</Label>
                <Input
                  value={editRowDraft.transporter || ''}
                  onChange={(e) => setEditRowDraft({ ...editRowDraft, transporter: e.target.value })}
                  placeholder="transporter"
                />
              </div>
              <div>
                <Label>Notes</Label>
                <Input
                  value={editRowDraft.notes || ''}
                  onChange={(e) => setEditRowDraft({ ...editRowDraft, notes: e.target.value })}
                  placeholder="notes"
                />
              </div>
            </div>
            <div className="mt-5 flex items-center justify-end gap-2">
              <Button
                variant="outline"
                onClick={() => {
                  setEditRowIndex(null);
                  setEditRowDraft(null);
                }}
              >
                Cancel
              </Button>
              <Button onClick={applyEditRow}>Save</Button>
            </div>
          </div>
        </div>
      )}

      {deleteTarget && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
          <button
            className="absolute inset-0 bg-slate-950/70 backdrop-blur-sm"
            onClick={() => setDeleteTarget(null)}
            aria-label="Close delete confirm"
          />
          <div
            className="modal-shell modal-body relative w-full rounded-2xl border border-white/10 bg-slate-950/95 p-6 shadow-2xl"
            role="dialog"
            aria-modal="true"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="text-lg font-semibold font-display text-white">Delete Vehicle</div>
            <div className="mt-2 text-sm text-slate-300">
              Are you sure you want to delete vehicle {deleteTarget.plate_raw}?
              <span className="text-slate-400"> This cannot be undone.</span>
            </div>
            <div className="mt-5 flex items-center justify-end gap-2">
              <Button variant="outline" onClick={() => setDeleteTarget(null)} disabled={busy}>
                Cancel
              </Button>
              <Button
                variant="danger"
                onClick={() => {
                  const target = deleteTarget;
                  setDeleteTarget(null);
                  if (target) onDelete(target);
                }}
                disabled={busy}
              >
                Delete
              </Button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
