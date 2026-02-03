'use client';

import { useEffect, useMemo, useState } from 'react';
import { getUser } from '@/lib/auth';
import { createAnprVehicle, getAnprVehicles, updateAnprVehicle, getGodowns, importAnprVehiclesCsv } from '@/lib/api';
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
        const items = Array.isArray(resp) ? resp : resp.items;
        if (alive) setGodowns(items || []);
      } catch {
        // Non-blocking.
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

  useEffect(() => {
    if (!importOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setImportOpen(false);
    };
    document.addEventListener('keydown', onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = prev;
    };
  }, [importOpen]);

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
    const nextTransporter = window.prompt('Transporter (blank to clear):', v.transporter || '') ?? null;
    if (nextTransporter === null) return;
    const nextNotes = window.prompt('Notes (blank to clear):', v.notes || '') ?? null;
    if (nextNotes === null) return;
    const nextListType =
      (window.prompt('List Type (WHITELIST or BLACKLIST):', (v.list_type || 'WHITELIST').toString()) ?? '').toUpperCase();
    if (!nextListType) return;
    if (nextListType !== 'WHITELIST' && nextListType !== 'BLACKLIST') {
      window.alert('Invalid list type. Use WHITELIST or BLACKLIST.');
      return;
    }
    try {
      setBusy(true);
      setError(null);
      await updateAnprVehicle(v.id, {
        transporter: nextTransporter.trim() ? nextTransporter.trim() : null,
        notes: nextNotes.trim() ? nextNotes.trim() : null,
        list_type: nextListType
      });
      await load();
    } catch (e: any) {
      setError(e?.message || 'Failed to update vehicle');
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
      const resp = await importAnprVehiclesCsv({ godown_id: godownId, file: importFile });
      setImportResult(resp);
      await load();
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
          <div className="text-sm text-slate-300">Maintain lists, import CSVs, and manage plate status per godown.</div>
        </div>
        <div className="hud-card p-4 min-w-[220px]">
          <div className="hud-label">Active / Total</div>
          <div className="hud-value">{stats.active} / {stats.total}</div>
          <div className="text-xs text-slate-500">Scope: {godownId ? godownId : 'Select godown'}</div>
        </div>
      </div>
      {error && <ErrorBanner message={error} />}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
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
              <Input value={plateText} onChange={(e) => setPlateText(e.target.value)} placeholder="e.g. WB23D5690" />
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
              <Input value={transporter} onChange={(e) => setTransporter(e.target.value)} placeholder="optional" />
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

        <Card className="hud-card">
          <CardHeader className="flex items-center justify-between">
            <div className="text-lg font-semibold font-display">Import Vehicles (CSV)</div>
            <div className="hud-pill">Bulk load</div>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="text-sm text-slate-300">
              Upload a CSV to add/update plates in bulk. Preview rows before import.
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Button onClick={() => setImportOpen(true)}>Open Import</Button>
              <div className="text-xs text-slate-400">Columns: plate_text, list_type, transporter, notes, is_active</div>
            </div>
            {importResult && (
              <div className="text-xs text-slate-300">
                Imported: {importResult.total} | Created: {importResult.created} | Updated: {importResult.updated} | Failed: {importResult.failed}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <Card className="hud-card">
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
                  <TH>Actions</TH>
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
                      <TD className="font-semibold">{v.plate_raw}</TD>
                      <TD>
                        <Badge
                          className={
                            (v.list_type || 'WHITELIST').toUpperCase() === 'BLACKLIST'
                              ? 'bg-red-100 text-red-800 border border-red-200'
                              : 'bg-blue-100 text-blue-800 border border-blue-200'
                          }
                        >
                          {(v.list_type || 'WHITELIST').toUpperCase()}
                        </Badge>
                      </TD>
                      <TD>
                        {v.is_active ? (
                          <Badge className="bg-green-100 text-green-800 border border-green-200">ACTIVE</Badge>
                        ) : (
                          <Badge className="bg-slate-100 text-slate-700 border border-slate-200">INACTIVE</Badge>
                        )}
                      </TD>
                      <TD>{v.transporter || 'N/A'}</TD>
                      <TD className="max-w-[360px] truncate">{v.notes || 'N/A'}</TD>
                      <TD className="space-x-2">
                        <Button
                          variant="outline"
                          className="px-3 py-1.5 text-xs"
                          onClick={() => onToggleActive(v)}
                          disabled={busy}
                        >
                          Toggle
                        </Button>
                        <Button
                          variant="outline"
                          className="px-3 py-1.5 text-xs"
                          onClick={() => onQuickEdit(v)}
                          disabled={busy}
                        >
                          Edit
                        </Button>
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
    {importOpen && (
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
        <button
          className="absolute inset-0 bg-slate-950/80 backdrop-blur-md"
          onClick={() => setImportOpen(false)}
          aria-label="Close import"
        />
        <div
          className="relative w-full max-w-3xl hud-card overflow-hidden animate-fade-up border border-white/10 shadow-2xl"
          onClick={(e) => e.stopPropagation()}
          role="dialog"
          aria-modal="true"
        >
          <div className="p-6 sm:p-8 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-xl font-semibold font-display text-white">Import Vehicles (CSV)</div>
                <div className="text-xs text-slate-400">Bulk load plates into the registry.</div>
              </div>
              <Button variant="outline" onClick={() => setImportOpen(false)}>
                Close
              </Button>
            </div>

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

            <div className="flex items-center justify-between gap-2">
              <div className="text-xs text-slate-400">
                Columns: plate_text, list_type, transporter, notes, is_active
              </div>
              <Button onClick={onImportCsv} disabled={importBusy || !importFile || !godownId}>
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
                      </TR>
                    </THead>
                    <TBody>
                      {importRows.map((r, idx) => (
                        <TR key={`${r.plate_text}-${idx}`}>
                          <TD className="font-semibold">{r.plate_text || 'N/A'}</TD>
                          <TD>{r.list_type || 'N/A'}</TD>
                          <TD>{r.transporter || 'N/A'}</TD>
                          <TD className="max-w-[360px] truncate">{r.notes || 'N/A'}</TD>
                          <TD>{r.is_active || 'N/A'}</TD>
                          <TD className="text-xs text-amber-300">{r.error || 'N/A'}</TD>
                        </TR>
                      ))}
                    </TBody>
                  </Table>
                </div>
              </div>
            )}

            {importResult && (
              <div className="text-xs text-slate-300">
                Imported: {importResult.total} | Created: {importResult.created} | Updated: {importResult.updated} | Failed: {importResult.failed}
              </div>
            )}
          </div>
        </div>
      </div>
    )}
    </>
  );
}
