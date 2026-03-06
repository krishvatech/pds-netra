'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { AlertBox } from '@/components/ui/alert-box';
import { ApiError, createRule, deleteRule, getCameras, getRuleTypes, getRules, getZones, updateRule } from '@/lib/api';
import { getSessionUser } from '@/lib/auth';
import type { Camera, Rule, RuleType, Zone } from '@/lib/types';

type FormMode = 'create' | 'edit';

type RuleFormState = {
  rule_name: string;
  rule_type_id: string;
};

const EMPTY_FORM: RuleFormState = { rule_name: '', rule_type_id: '' };

function formatDate(value: string) {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
}

export default function RulesPage() {
  const router = useRouter();
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [zones, setZones] = useState<Zone[]>([]);
  const [rules, setRules] = useState<Rule[]>([]);
  const [ruleTypes, setRuleTypes] = useState<RuleType[]>([]);

  const [selectedCameraId, setSelectedCameraId] = useState('');
  const [selectedZoneId, setSelectedZoneId] = useState('');

  const [loading, setLoading] = useState(true);
  const [loadingZones, setLoadingZones] = useState(false);
  const [loadingRules, setLoadingRules] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const [showForm, setShowForm] = useState(false);
  const [formMode, setFormMode] = useState<FormMode>('create');
  const [formData, setFormData] = useState<RuleFormState>(EMPTY_FORM);
  const [activeRule, setActiveRule] = useState<Rule | null>(null);

  useEffect(() => {
    async function guardAndLoad() {
      const sessionUser = await getSessionUser();
      if (!sessionUser) {
        router.replace('/auth/login');
        return;
      }
      await loadInitial();
    }
    guardAndLoad();
  }, [router]);

  async function loadInitial() {
    setLoading(true);
    setError(null);
    try {
      const [cameraList, ruleTypeList] = await Promise.all([getCameras(), getRuleTypes()]);
      setCameras(cameraList);
      setRuleTypes(ruleTypeList);
      const nextCameraId = cameraList[0]?.id || '';
      setSelectedCameraId(nextCameraId);
    } catch (err) {
      setError('Unable to load rule setup right now.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    let cancelled = false;
    async function loadZonesForCamera() {
      if (!selectedCameraId) {
        setZones([]);
        setSelectedZoneId('');
        setRules([]);
        return;
      }
      setLoadingZones(true);
      setActionError(null);
      try {
        const zoneList = await getZones(selectedCameraId);
        if (cancelled) return;
        setZones(zoneList);
        setSelectedZoneId((prev) => {
          if (zoneList.find((zone) => zone.id === prev)) return prev;
          return zoneList[0]?.id || '';
        });
      } catch (err) {
        if (!cancelled) {
          setActionError('Unable to load zones for this camera.');
          setZones([]);
          setSelectedZoneId('');
          setRules([]);
        }
      } finally {
        if (!cancelled) setLoadingZones(false);
      }
    }
    loadZonesForCamera();
    return () => {
      cancelled = true;
    };
  }, [selectedCameraId]);

  useEffect(() => {
    let cancelled = false;
    async function loadRulesForZone() {
      if (!selectedZoneId) {
        setRules([]);
        return;
      }
      setLoadingRules(true);
      setActionError(null);
      try {
        const ruleList = await getRules(selectedZoneId);
        if (!cancelled) setRules(ruleList);
      } catch (err) {
        if (!cancelled) {
          setActionError('Unable to load rules for this zone.');
          setRules([]);
        }
      } finally {
        if (!cancelled) setLoadingRules(false);
      }
    }
    loadRulesForZone();
    return () => {
      cancelled = true;
    };
  }, [selectedZoneId]);

  const ruleTypeById = useMemo(() => {
    const map = new Map<string, RuleType>();
    ruleTypes.forEach((ruleType) => map.set(ruleType.id, ruleType));
    return map;
  }, [ruleTypes]);

  const selectedCamera = useMemo(
    () => cameras.find((camera) => camera.id === selectedCameraId) || null,
    [cameras, selectedCameraId]
  );
  const selectedZone = useMemo(
    () => zones.find((zone) => zone.id === selectedZoneId) || null,
    [zones, selectedZoneId]
  );
  const totalRules = useMemo(() => rules.length, [rules]);

  function updateField(field: keyof RuleFormState, value: string) {
    setFormData((prev) => ({ ...prev, [field]: value }));
  }

  function openCreate() {
    if (saving) return;
    if (cameras.length === 0) {
      setActionError('Add a camera before creating rules.');
      return;
    }
    if (!selectedCameraId && cameras.length > 0) {
      setSelectedCameraId(cameras[0].id);
    }
    if (ruleTypes.length === 0) {
      setActionError('No rule types available. Ask an admin to add rule types.');
      return;
    }
    setFormMode('create');
    setActiveRule(null);
    setFormData({ rule_name: '', rule_type_id: ruleTypes[0]?.id || '' });
    setActionError(null);
    setSuccess(null);
    setShowForm(true);
  }

  function openEdit(rule: Rule) {
    if (saving) return;
    setFormMode('edit');
    setActiveRule(rule);
    setFormData({ rule_name: rule.rule_name, rule_type_id: rule.rule_type_id });
    setActionError(null);
    setSuccess(null);
    setShowForm(true);
  }

  function closeForm() {
    if (saving) return;
    setShowForm(false);
    setActionError(null);
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (saving) return;
    setActionError(null);
    setSuccess(null);

    if (!selectedZoneId) {
      setActionError('Select a zone first.');
      return;
    }

    const name = formData.rule_name.trim();
    const ruleTypeId = formData.rule_type_id;
    if (!name || !ruleTypeId) {
      setActionError('Rule name and rule type are required.');
      return;
    }

    try {
      setSaving(true);
      if (formMode === 'create') {
        const created = await createRule(selectedZoneId, { rule_name: name, rule_type_id: ruleTypeId });
        setRules((prev) => [created, ...prev]);
        setSuccess('Rule created.');
        setShowForm(false);
      } else if (activeRule) {
        const updated = await updateRule(selectedZoneId, activeRule.id, {
          rule_name: name,
          rule_type_id: ruleTypeId
        });
        setRules((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
        setFormMode('create');
        setActiveRule(null);
        setSuccess('Rule updated.');
        setShowForm(false);
      }
      setFormData(EMPTY_FORM);
    } catch (err) {
      if (err instanceof ApiError) {
        setActionError('Unable to save rule. Please try again.');
      } else {
        setActionError('Unable to save rule. Please try again.');
      }
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(rule: Rule) {
    if (saving) return;
    const ok = window.confirm(`Delete rule "${rule.rule_name}"? This cannot be undone.`);
    if (!ok) return;
    setActionError(null);
    setSuccess(null);
    try {
      setSaving(true);
      await deleteRule(selectedZoneId, rule.id);
      setRules((prev) => prev.filter((item) => item.id !== rule.id));
      if (activeRule?.id === rule.id) {
        setFormMode('create');
        setActiveRule(null);
        setFormData(EMPTY_FORM);
      }
      setSuccess('Rule deleted.');
    } catch (err) {
      setActionError('Unable to delete rule. Please try again.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="space-y-2">
          <div className="hud-pill">
            <span className="pulse-dot pulse-info" />
            Zone Configuration
          </div>
          <div className="text-3xl sm:text-4xl font-semibold font-display tracking-tight text-slate-100 drop-shadow">
            Rules
          </div>
          <div className="text-sm text-slate-300">
            Assign detection rule types to zones for each camera feed.
          </div>
        </div>
        <div className="flex w-full flex-wrap items-center gap-3 lg:w-auto">
          <div className="hud-card w-full px-4 py-2 text-center text-xs text-slate-300 sm:w-auto">
            Total {totalRules}
          </div>
          <button
            type="button"
            className="btn-primary w-full rounded-full px-5 py-2 text-center text-xs font-semibold uppercase tracking-[0.25em] sm:w-auto"
            onClick={openCreate}
          >
            Add Rule
          </button>
        </div>
      </div>

      {error && <AlertBox variant="error">{error}</AlertBox>}
      {!showForm && actionError && <AlertBox variant="error">{actionError}</AlertBox>}
      {!showForm && success && <AlertBox variant="success">{success}</AlertBox>}

      {loading ? (
        <div className="hud-card p-6 text-sm text-slate-300">Loading rule setup…</div>
      ) : cameras.length === 0 ? (
        <div className="hud-card p-6">
          <div className="text-lg font-semibold font-display">No cameras found</div>
          <div className="text-sm text-slate-400 mt-2">Add a camera first to configure zones and rules.</div>
        </div>
      ) : ruleTypes.length === 0 ? (
        <div className="hud-card p-6">
          <div className="text-lg font-semibold font-display">No rule types found</div>
          <div className="text-sm text-slate-400 mt-2">Ask an admin to create rule types.</div>
        </div>
      ) : (
        <div className="space-y-6">
          {loadingZones || loadingRules ? (
            <div className="hud-card p-6 text-sm text-slate-300">Loading rules…</div>
          ) : zones.length === 0 ? (
            <div className="hud-card p-6">
              <div className="text-lg font-semibold font-display">No zones yet</div>
              <div className="text-sm text-slate-400 mt-2">Create a zone first, then assign rules.</div>
            </div>
          ) : rules.length === 0 ? (
            <div className="hud-card p-6">
              <div className="text-lg font-semibold font-display">No rules for this zone</div>
              <div className="text-sm text-slate-400 mt-2">Add a rule type to start monitoring.</div>
            </div>
          ) : (
            <div className="table-shell table-shell-no-scroll hidden md:block">
              <table className="w-full table-fixed text-sm">
                <thead>
                  <tr>
                    <th className="text-left px-6 w-[30%]">Rule Name</th>
                    <th className="text-left px-6 w-[30%]">Rule Type</th>
                    <th className="text-right px-6 w-[20%]">Created</th>
                    <th className="text-right px-6 w-[20%]">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {rules.map((rule) => {
                    const ruleType = ruleTypeById.get(rule.rule_type_id);
                    return (
                      <tr key={rule.id}>
                        <td className="px-6 font-medium text-slate-100 w-[30%]">{rule.rule_name}</td>
                        <td className="px-6 text-slate-400 w-[30%]">
                          {ruleType ? ruleType.rule_type_name : 'Unknown'}
                        </td>
                        <td className="px-6 text-right text-slate-400 w-[20%]">{formatDate(rule.created_at)}</td>
                        <td className="px-6 text-right w-[20%]">
                          <div className="flex items-center justify-end gap-2">
                            <button
                              type="button"
                              aria-label="Edit rule"
                              className="flex h-8 w-8 items-center justify-center rounded-full border border-white/15 text-slate-200 hover:border-white/30 hover:text-white"
                              onClick={() => openEdit(rule)}
                              disabled={saving}
                            >
                              <svg
                                viewBox="0 0 24 24"
                                className="h-4 w-4"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="2"
                              >
                                <path d="M12 20h9" />
                                <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z" />
                              </svg>
                            </button>
                            <button
                              type="button"
                              aria-label="Delete rule"
                              className="flex h-8 w-8 items-center justify-center rounded-full border border-red-400/30 text-red-300 hover:border-red-400/60 hover:text-red-200"
                              onClick={() => handleDelete(rule)}
                              disabled={saving}
                            >
                              <svg
                                viewBox="0 0 24 24"
                                className="h-4 w-4"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="2"
                              >
                                <path d="M3 6h18" />
                                <path d="M8 6V4h8v2" />
                                <path d="M10 11v6M14 11v6" />
                                <path d="M6 6l1 14h10l1-14" />
                              </svg>
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {!loadingRules && rules.length > 0 && (
            <div className="space-y-3 md:hidden">
              {rules.map((rule) => {
                const ruleType = ruleTypeById.get(rule.rule_type_id);
                return (
                  <div key={rule.id} className="hud-card p-4">
                    <div className="text-xs uppercase tracking-[0.3em] text-slate-500">Rule</div>
                    <div className="mt-1 text-base font-semibold text-slate-100">{rule.rule_name}</div>
                    <div className="mt-2 text-xs text-slate-400">
                      Type: {ruleType ? ruleType.rule_type_name : 'Unknown'}
                    </div>
                    <div className="mt-2 text-xs text-slate-500">Created {formatDate(rule.created_at)}</div>
                    <div className="mt-4 flex items-center gap-2">
                      <button
                        type="button"
                        aria-label="Edit rule"
                        className="flex h-8 w-8 items-center justify-center rounded-full border border-white/15 text-slate-200 hover:border-white/30 hover:text-white"
                        onClick={() => openEdit(rule)}
                        disabled={saving}
                      >
                        <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
                          <path d="M12 20h9" />
                          <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z" />
                        </svg>
                      </button>
                      <button
                        type="button"
                        aria-label="Delete rule"
                        className="flex h-8 w-8 items-center justify-center rounded-full border border-red-400/30 text-red-300 hover:border-red-400/60 hover:text-red-200"
                        onClick={() => handleDelete(rule)}
                        disabled={saving}
                      >
                        <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
                          <path d="M3 6h18" />
                          <path d="M8 6V4h8v2" />
                          <path d="M10 11v6M14 11v6" />
                          <path d="M6 6l1 14h10l1-14" />
                        </svg>
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 px-4 py-6 backdrop-blur-sm">
          <div className="hud-card modal-shell p-6">
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="text-xs uppercase tracking-[0.3em] text-slate-400">
                  {formMode === 'create' ? 'New Rule' : 'Edit Rule'}
                </div>
                <div className="text-xl font-semibold font-display text-slate-100 mt-2">
                  {formMode === 'create' ? 'Add rule' : 'Update rule'}
                </div>
              </div>
              <button
                type="button"
                aria-label="Close"
                className="flex h-8 w-8 items-center justify-center rounded-full border border-white/10 text-slate-300 hover:border-white/30 hover:text-slate-100"
                onClick={closeForm}
              >
                <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M18 6 6 18M6 6l12 12" />
                </svg>
              </button>
            </div>

            <form className="modal-body mt-6 space-y-4" onSubmit={handleSubmit}>
              <div className="grid grid-cols-1 gap-4">
                <div className="space-y-2">
                  <label className="text-[11px] font-semibold uppercase tracking-[0.3em] text-slate-300/80">
                    Camera
                  </label>
                  <select
                    className="w-full rounded-lg border border-white/15 bg-white/5 px-4 py-2.5 text-sm text-slate-100 shadow-inner focus:border-sky-300/60 focus:outline-none focus:ring-2 focus:ring-sky-300/20"
                    value={selectedCameraId}
                    onChange={(event) => setSelectedCameraId(event.target.value)}
                    disabled={formMode === 'edit' || cameras.length === 0}
                  >
                    {cameras.map((camera) => (
                      <option key={camera.id} value={camera.id} className="bg-slate-900">
                        {camera.camera_name}
                      </option>
                    ))}
                  </select>
                  {selectedCamera && (
                    <div className="text-xs text-slate-400">Role: {selectedCamera.role}</div>
                  )}
                </div>
                <div className="space-y-2">
                  <label className="text-[11px] font-semibold uppercase tracking-[0.3em] text-slate-300/80">
                    Zone
                  </label>
                  <select
                    className="w-full rounded-lg border border-white/15 bg-white/5 px-4 py-2.5 text-sm text-slate-100 shadow-inner focus:border-sky-300/60 focus:outline-none focus:ring-2 focus:ring-sky-300/20"
                    value={selectedZoneId}
                    onChange={(event) => setSelectedZoneId(event.target.value)}
                    disabled={formMode === 'edit' || loadingZones || zones.length === 0}
                  >
                    {zones.length === 0 && <option className="bg-slate-900">No zones available</option>}
                    {zones.map((zone) => (
                      <option key={zone.id} value={zone.id} className="bg-slate-900">
                        {zone.zone_name}
                      </option>
                    ))}
                  </select>
                  {selectedZone && (
                    <div className="text-xs text-slate-400">
                      {selectedZone.is_active ? 'Active' : 'Inactive'} · {selectedZone.polygon.length} points
                    </div>
                  )}
                </div>
                <div className="space-y-2">
                  <label className="text-[11px] font-semibold uppercase tracking-[0.3em] text-slate-300/80">
                    Rule type
                  </label>
                  <select
                    className="w-full rounded-lg border border-white/15 bg-white/5 px-4 py-2.5 text-sm text-slate-100 placeholder:text-slate-400/70 shadow-inner focus:border-sky-300/60 focus:outline-none focus:ring-2 focus:ring-sky-300/20"
                    value={formData.rule_type_id}
                    onChange={(event) => updateField('rule_type_id', event.target.value)}
                  >
                    {ruleTypes.map((ruleType) => (
                      <option key={ruleType.id} value={ruleType.id} className="bg-slate-900">
                        {ruleType.rule_type_name}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="space-y-2">
                  <label className="text-[11px] font-semibold uppercase tracking-[0.3em] text-slate-300/80">
                    Rule name
                  </label>
                  <input
                    type="text"
                    className="w-full rounded-lg border border-white/15 bg-white/5 px-4 py-2.5 text-sm text-slate-100 placeholder:text-slate-400/70 shadow-inner focus:border-sky-300/60 focus:outline-none focus:ring-2 focus:ring-sky-300/20"
                    placeholder="Fire detection"
                    value={formData.rule_name}
                    onChange={(event) => updateField('rule_name', event.target.value)}
                  />
                </div>
              </div>

              {actionError && <AlertBox variant="error">{actionError}</AlertBox>}
              {success && <AlertBox variant="success">{success}</AlertBox>}

              <div className="flex flex-wrap items-center justify-end gap-3">
                <button
                  type="submit"
                  className="btn-primary rounded-full px-5 py-2 text-xs font-semibold uppercase tracking-[0.25em] disabled:cursor-not-allowed disabled:opacity-60"
                  disabled={saving}
                >
                  {saving ? 'Saving…' : formMode === 'create' ? 'Add Rule' : 'Update Rule'}
                </button>
                {formMode === 'edit' && (
                  <button
                    type="button"
                    className="rounded-full border border-white/10 bg-white/5 px-5 py-2 text-xs font-semibold uppercase tracking-[0.25em] text-slate-200 hover:border-white/20 hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-60"
                    onClick={closeForm}
                    disabled={saving}
                  >
                    Cancel
                  </button>
                )}
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
