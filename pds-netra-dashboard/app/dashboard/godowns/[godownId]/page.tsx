'use client';

import { useEffect, useMemo, useState } from 'react';
import { getGodowns, createGodown, updateGodown, deleteGodown } from '@/lib/api';
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

  // Add Godown form state
  const [showAddForm, setShowAddForm] = useState(false);
  const [newGodown, setNewGodown] = useState({
    godown_id: '',
    name: '',
    district: '',
    code: ''
  });
  const [addLoading, setAddLoading] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);
  const [addSuccess, setAddSuccess] = useState(false);

  // Edit mode
  const [editingId, setEditingId] = useState<string | null>(null);

  const activeFilters = useMemo(() => {
    const chips: string[] = [];
    if (district.trim()) chips.push(`District: ${district.trim()}`);
    if (status) chips.push(`Status: ${status}`);
    return chips;
  }, [district, status]);

  const loadGodowns = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getGodowns({ district: district || undefined, status: status || undefined });
      setItems(Array.isArray(data) ? data : data.items);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load godowns');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadGodowns();
  }, [district, status]);

  const handleCreateGodown = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newGodown.godown_id.trim()) return;

    setAddLoading(true);
    setAddError(null);
    setAddSuccess(false);

    try {
      if (editingId) {
        await updateGodown(editingId, {
          name: newGodown.name.trim() || null,
          district: newGodown.district.trim() || null,
          code: newGodown.code.trim() || null
        });
      } else {
        await createGodown({
          godown_id: newGodown.godown_id.trim(),
          name: newGodown.name.trim() || undefined,
          district: newGodown.district.trim() || undefined,
          code: newGodown.code.trim() || undefined
        });
      }
      setAddSuccess(true);
      setNewGodown({ godown_id: '', name: '', district: '', code: '' });
      setEditingId(null);
      setShowAddForm(false);
      await loadGodowns();
      setTimeout(() => setAddSuccess(false), 3000);
    } catch (e) {
      setAddError(e instanceof Error ? e.message : 'Failed to save godown');
    } finally {
      setAddLoading(false);
    }
  };

  const handleEdit = (g: GodownListItem) => {
    setEditingId(g.godown_id);
    setNewGodown({
      godown_id: g.godown_id,
      name: g.name ?? '',
      district: g.district ?? '',
      code: '' // Code not in ListItem currently, but available in Detail? Backend has it.
    });
    setShowAddForm(true);
    setAddError(null);
    setAddSuccess(false);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleDelete = async (id: string) => {
    const confirmMessage = `⚠️ DELETE GODOWN: ${id}

This will permanently delete:
✗ The godown record
✗ All cameras
✗ All events and alerts
✗ All rules
✗ All test runs
✗ All media files (live feeds, recordings, snapshots)

This action CANNOT be undone!

Type the godown ID to confirm: ${id}`;

    const userInput = window.prompt(confirmMessage);
    if (userInput !== id) return;

    try {
      const result = await deleteGodown(id);
      await loadGodowns();

      // Show what was deleted
      if (result.deleted) {
        const summary = `Deleted: ${result.deleted.events || 0} events, ${result.deleted.alerts || 0} alerts, ${result.deleted.test_runs || 0} test runs, ${result.deleted.media_directories?.length || 0} media directories`;
        alert(`✓ ${result.message}\n\n${summary}`);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to delete godown');
    }
  };

  const districts = useMemo(() => {
    const unique = new Set(items.map((g) => g.district).filter(Boolean) as string[]);
    return Array.from(unique).sort();
  }, [items]);

  const districtOptions = useMemo(() => {
    return [{ label: 'All districts', value: '' }, ...districts.map((d) => ({ label: d, value: d }))];
  }, [districts]);

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="space-y-2">
          <div className="hud-pill">
            <span className="pulse-dot pulse-info" />
            Network view
          </div>
          <div className="text-4xl font-semibold font-display tracking-tight text-slate-100 drop-shadow">
            Godown Network
          </div>
          <div className="text-sm text-slate-300">Browse and filter monitored godowns.</div>
        </div>
        <button
          onClick={() => {
            if (showAddForm && editingId) {
              setEditingId(null);
              setNewGodown({ godown_id: '', name: '', district: '', code: '' });
            }
            setShowAddForm(!showAddForm);
          }}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md transition-colors text-sm font-medium self-start lg:self-center"
        >
          {showAddForm ? 'Cancel' : 'Add Godown'}
        </button>
      </div>

      {showAddForm && (
        <Card className="animate-fade-up hud-card border-blue-500/30">
          <CardHeader>
            <div className="text-lg font-semibold font-display">{editingId ? `Edit Godown: ${editingId}` : 'Add New Godown'}</div>
            <div className="text-sm text-slate-300">{editingId ? 'Update godown details.' : 'Register a new godown in the system.'}</div>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleCreateGodown} className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                <div className="space-y-1">
                  <label className="text-xs text-slate-400">Godown ID (Required)</label>
                  <input
                    type="text"
                    required
                    disabled={!!editingId}
                    placeholder="e.g. GDN_002"
                    className="w-full bg-slate-900 border border-slate-700 rounded px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500 disabled:opacity-50"
                    value={newGodown.godown_id}
                    onChange={(e) => setNewGodown({ ...newGodown, godown_id: e.target.value })}
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-xs text-slate-400">Name</label>
                  <input
                    type="text"
                    placeholder="e.g. Central Warehouse"
                    className="w-full bg-slate-900 border border-slate-700 rounded px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
                    value={newGodown.name}
                    onChange={(e) => setNewGodown({ ...newGodown, name: e.target.value })}
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-xs text-slate-400">District</label>
                  <input
                    type="text"
                    placeholder="e.g. City Central"
                    className="w-full bg-slate-900 border border-slate-700 rounded px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
                    value={newGodown.district}
                    onChange={(e) => setNewGodown({ ...newGodown, district: e.target.value })}
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-xs text-slate-400">Code</label>
                  <input
                    type="text"
                    placeholder="e.g. CW002"
                    className="w-full bg-slate-900 border border-slate-700 rounded px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
                    value={newGodown.code}
                    onChange={(e) => setNewGodown({ ...newGodown, code: e.target.value })}
                  />
                </div>
              </div>

              {addError && <ErrorBanner message={addError} />}
              {addSuccess && (
                <div className="text-sm text-green-400 bg-green-400/10 border border-green-400/20 rounded px-3 py-2">
                  Godown {editingId ? 'updated' : 'created'} successfully!
                </div>
              )}

              <div className="flex justify-end pt-2">
                <button
                  type="submit"
                  disabled={addLoading}
                  className="px-6 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-700 text-white rounded-md transition-colors text-sm font-medium"
                >
                  {addLoading ? (editingId ? 'Updating...' : 'Creating...') : (editingId ? 'Update Godown' : 'Create Godown')}
                </button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      <Card className="animate-fade-up hud-card">
        <CardHeader>
          <div className="text-lg font-semibold font-display">Filters</div>
          <div className="text-sm text-slate-300">Slice by district and status.</div>
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
                <span key={chip} className="hud-pill">
                  {chip}
                </span>
              ))}
            </div>
          )}

          <div className="mt-4">
            {error && <ErrorBanner message={error} onRetry={() => loadGodowns()} />}
            {loading ? (
              <div className="text-sm text-slate-600">Loading…</div>
            ) : (
              <GodownsTable
                items={items}
                onEdit={handleEdit}
                onDelete={handleDelete}
              />
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}