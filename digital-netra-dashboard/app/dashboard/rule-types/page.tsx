'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { AlertBox } from '@/components/ui/alert-box';
import { ApiError, createRuleType, deleteRuleType, getRuleTypes, updateRuleType } from '@/lib/api';
import { getSessionUser } from '@/lib/auth';
import type { RuleType, RuleTypeUpdate } from '@/lib/types';

type FormMode = 'create' | 'edit';

const EMPTY_FORM: RuleTypeUpdate = {
  rule_type_name: '',
  rule_type_slug: '',
  model_name: ''
};

function formatDate(value: string) {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
}

export default function RuleTypesPage() {
  const router = useRouter();
  const [ruleTypes, setRuleTypes] = useState<RuleType[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [formData, setFormData] = useState<RuleTypeUpdate>(EMPTY_FORM);
  const [formMode, setFormMode] = useState<FormMode>('create');
  const [activeRuleType, setActiveRuleType] = useState<RuleType | null>(null);

  useEffect(() => {
    async function guardAndLoad() {
      const sessionUser = await getSessionUser();
      if (!sessionUser) {
        router.replace('/auth/login');
        return;
      }
      if (!sessionUser.is_admin) {
        router.replace('/dashboard');
        return;
      }
      await loadRuleTypes();
    }
    guardAndLoad();
  }, [router]);

  async function loadRuleTypes() {
    setLoading(true);
    setError(null);
    try {
      const data = await getRuleTypes();
      setRuleTypes(data);
    } catch (err) {
      setError('Unable to load rule types right now.');
    } finally {
      setLoading(false);
    }
  }

  const totalCount = useMemo(() => ruleTypes.length, [ruleTypes]);

  function updateField(field: keyof RuleTypeUpdate, value: string) {
    setFormData((prev) => ({ ...prev, [field]: value }));
  }

  function openCreate() {
    if (saving) return;
    setFormMode('create');
    setActiveRuleType(null);
    setFormData(EMPTY_FORM);
    setActionError(null);
    setSuccess(null);
  }

  function openEdit(ruleType: RuleType) {
    if (saving) return;
    setFormMode('edit');
    setActiveRuleType(ruleType);
    setFormData({
      rule_type_name: ruleType.rule_type_name,
      rule_type_slug: ruleType.rule_type_slug,
      model_name: ruleType.model_name
    });
    setActionError(null);
    setSuccess(null);
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (saving) return;
    setActionError(null);
    setSuccess(null);

    const name = formData.rule_type_name.trim();
    const slug = formData.rule_type_slug.trim();
    const modelName = formData.model_name.trim();

    if (!name || !slug || !modelName) {
      setActionError('All fields are required.');
      return;
    }

    try {
      setSaving(true);
      if (formMode === 'create') {
        const created = await createRuleType({
          rule_type_name: name,
          rule_type_slug: slug,
          model_name: modelName
        });
        setRuleTypes((prev) => [created, ...prev]);
        setFormData(EMPTY_FORM);
        setSuccess('Rule type created.');
      } else if (activeRuleType) {
        const updated = await updateRuleType(activeRuleType.id, {
          rule_type_name: name,
          rule_type_slug: slug,
          model_name: modelName
        });
        setRuleTypes((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
        setFormMode('create');
        setActiveRuleType(null);
        setFormData(EMPTY_FORM);
        setSuccess('Rule type updated.');
      }
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 409 && err.body?.detail === 'rule_type_slug_taken') {
          setActionError('Slug already exists. Please choose another.');
        } else if (err.status === 409 && err.body?.detail === 'rule_type_name_taken') {
          setActionError('Rule type name already exists.');
        } else {
          setActionError('Unable to save rule type. Please try again.');
        }
      } else {
        setActionError('Unable to save rule type. Please try again.');
      }
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(ruleType: RuleType) {
    if (saving) return;
    const ok = window.confirm(`Delete rule type "${ruleType.rule_type_name}"? This cannot be undone.`);
    if (!ok) return;
    setActionError(null);
    setSuccess(null);
    try {
      setSaving(true);
      await deleteRuleType(ruleType.id);
      setRuleTypes((prev) => prev.filter((item) => item.id !== ruleType.id));
      if (activeRuleType?.id === ruleType.id) {
        setFormMode('create');
        setActiveRuleType(null);
        setFormData(EMPTY_FORM);
      }
      setSuccess('Rule type deleted.');
    } catch (err) {
      setActionError('Unable to delete rule type. Please try again.');
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
            Administration
          </div>
          <div className="text-3xl sm:text-4xl font-semibold font-display tracking-tight text-slate-100 drop-shadow">
            Rule Types
          </div>
          <div className="text-sm text-slate-300">Define reusable rule categories for the platform.</div>
        </div>
        <div className="flex w-full flex-wrap items-center gap-3 lg:w-auto">
          <div className="hud-card w-full px-4 py-2 text-center text-xs text-slate-300 sm:w-auto">
            Total {totalCount}
          </div>
        </div>
      </div>

      {error && <AlertBox variant="error">{error}</AlertBox>}

      <div className="hud-card p-6">
        <form className="space-y-4" onSubmit={handleSubmit}>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <div className="space-y-2">
              <label className="hud-label" htmlFor="ruleTypeName">Rule type name</label>
              <input
                id="ruleTypeName"
                type="text"
                className="w-full rounded-lg border border-white/15 bg-white/5 px-4 py-2.5 text-sm text-slate-100 placeholder:text-slate-400/70 shadow-inner focus:border-sky-300/60 focus:outline-none focus:ring-2 focus:ring-sky-300/20"
                placeholder="Fire detection"
                value={formData.rule_type_name}
                onChange={(event) => updateField('rule_type_name', event.target.value)}
              />
            </div>
            <div className="space-y-2">
              <label className="hud-label" htmlFor="ruleTypeSlug">Rule type slug</label>
              <input
                id="ruleTypeSlug"
                type="text"
                className="w-full rounded-lg border border-white/15 bg-white/5 px-4 py-2.5 text-sm text-slate-100 placeholder:text-slate-400/70 shadow-inner focus:border-sky-300/60 focus:outline-none focus:ring-2 focus:ring-sky-300/20"
                placeholder="fire_detection"
                value={formData.rule_type_slug}
                onChange={(event) => updateField('rule_type_slug', event.target.value)}
              />
            </div>
            <div className="space-y-2">
              <label className="hud-label" htmlFor="modelName">Model name</label>
              <input
                id="modelName"
                type="text"
                className="w-full rounded-lg border border-white/15 bg-white/5 px-4 py-2.5 text-sm text-slate-100 placeholder:text-slate-400/70 shadow-inner focus:border-sky-300/60 focus:outline-none focus:ring-2 focus:ring-sky-300/20"
                placeholder="FireDetector"
                value={formData.model_name}
                onChange={(event) => updateField('model_name', event.target.value)}
              />
            </div>
          </div>

          {actionError && <AlertBox variant="error">{actionError}</AlertBox>}
          {success && <AlertBox variant="success">{success}</AlertBox>}

          <div className="flex flex-wrap items-center gap-3">
            <button
              type="submit"
              className="btn-primary rounded-full px-5 py-2 text-xs font-semibold uppercase tracking-[0.25em] disabled:cursor-not-allowed disabled:opacity-60"
              disabled={saving}
            >
              {saving ? 'Saving…' : formMode === 'create' ? 'Add Rule Type' : 'Update Rule Type'}
            </button>
            {formMode === 'edit' && (
              <button
                type="button"
                className="rounded-full border border-white/10 bg-white/5 px-5 py-2 text-xs font-semibold uppercase tracking-[0.25em] text-slate-200 hover:border-white/20 hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-60"
                onClick={openCreate}
                disabled={saving}
              >
                Cancel
              </button>
            )}
          </div>
        </form>
      </div>

      {loading ? (
        <div className="hud-card p-6 text-sm text-slate-300">Loading rule types…</div>
      ) : ruleTypes.length === 0 ? (
        <div className="hud-card p-6 text-sm text-slate-300">No rule types created yet.</div>
      ) : (
        <div className="table-shell table-shell-no-scroll hidden md:block">
          <table className="w-full table-fixed text-sm">
            <thead>
              <tr>
                <th className="text-left px-6 w-[25%]">Name</th>
                <th className="text-left px-6 w-[22%]">Slug</th>
                <th className="text-left px-6 w-[23%]">Model</th>
                <th className="text-right px-6 w-[15%]">Created</th>
                <th className="text-right px-6 w-[15%]">Actions</th>
              </tr>
            </thead>
            <tbody>
              {ruleTypes.map((ruleType) => (
                <tr key={ruleType.id}>
                  <td className="px-6 font-medium text-slate-100 w-[25%]">{ruleType.rule_type_name}</td>
                  <td className="px-6 text-slate-400 w-[22%]">{ruleType.rule_type_slug}</td>
                  <td className="px-6 text-slate-400 w-[23%]">{ruleType.model_name}</td>
                  <td className="px-6 text-right text-slate-400 w-[15%]">{formatDate(ruleType.created_at)}</td>
                  <td className="px-6 text-right w-[15%]">
                    <div className="flex items-center justify-end gap-2">
                      <button
                        type="button"
                        className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-200 hover:border-white/20 hover:bg-white/10"
                        onClick={() => openEdit(ruleType)}
                        disabled={saving}
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        className="rounded-full border border-red-500/30 bg-red-500/10 px-3 py-1 text-xs text-red-200 hover:border-red-500/60 hover:bg-red-500/20"
                        onClick={() => handleDelete(ruleType)}
                        disabled={saving}
                      >
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!loading && ruleTypes.length > 0 && (
        <div className="space-y-3 md:hidden">
          {ruleTypes.map((ruleType) => (
            <div key={ruleType.id} className="hud-card p-4">
              <div className="text-xs uppercase tracking-[0.3em] text-slate-500">Rule type</div>
              <div className="mt-1 text-base font-semibold text-slate-100">{ruleType.rule_type_name}</div>
              <div className="mt-2 text-xs text-slate-400">Slug: {ruleType.rule_type_slug}</div>
              <div className="text-xs text-slate-400">Model: {ruleType.model_name}</div>
              <div className="mt-3 text-xs text-slate-500">Created {formatDate(ruleType.created_at)}</div>
              <div className="mt-4 flex items-center gap-2">
                <button
                  type="button"
                  className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-200 hover:border-white/20 hover:bg-white/10"
                  onClick={() => openEdit(ruleType)}
                  disabled={saving}
                >
                  Edit
                </button>
                <button
                  type="button"
                  className="rounded-full border border-red-500/30 bg-red-500/10 px-3 py-1 text-xs text-red-200 hover:border-red-500/60 hover:bg-red-500/20"
                  onClick={() => handleDelete(ruleType)}
                  disabled={saving}
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
