'use client';

import { useEffect, useMemo, useState } from 'react';
import {
  createRule,
  deleteRule,
  getAfterHoursPolicy,
  getCameraZones,
  getGodownDetail,
  getGodowns,
  getRules,
  updateAfterHoursPolicy,
  updateRule
} from '@/lib/api';
import type { AfterHoursPolicy, GodownListItem, RuleItem } from '@/lib/types';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Select } from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Table, THead, TBody, TR, TH, TD } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { formatUtc } from '@/lib/formatters';

type FieldDef = {
  key: string;
  label: string;
  type: 'text' | 'number' | 'checkbox' | 'list';
  placeholder?: string;
};

const RULE_TYPES: Array<{ value: string; label: string; fields: FieldDef[] }> = [
  {
    value: 'UNAUTH_PERSON_AFTER_HOURS',
    label: 'Unauthorized Person After Hours',
    fields: [
      { key: 'start_time', label: 'Start time (HH:MM)', type: 'text', placeholder: '22:00' },
      { key: 'end_time', label: 'End time (HH:MM)', type: 'text', placeholder: '06:00' }
    ]
  },
  {
    value: 'NO_PERSON_DURING',
    label: 'No Person During',
    fields: [
      { key: 'start', label: 'Start time (HH:MM)', type: 'text', placeholder: '00:00' },
      { key: 'end', label: 'End time (HH:MM)', type: 'text', placeholder: '23:59' }
    ]
  },
  { value: 'LOITERING', label: 'Loitering', fields: [{ key: 'threshold_seconds', label: 'Threshold (sec)', type: 'number', placeholder: '120' }] },
  { value: 'ANIMAL_FORBIDDEN', label: 'Animal Forbidden', fields: [] },
  {
    value: 'PHONE_USAGE',
    label: 'Phone Usage',
    fields: [
      { key: 'start_time', label: 'Start time (HH:MM)', type: 'text', placeholder: '09:00' },
      { key: 'end_time', label: 'End time (HH:MM)', type: 'text', placeholder: '19:00' },
      { key: 'cooldown_seconds', label: 'Cooldown (sec)', type: 'number', placeholder: '30' }
    ]
  },
  {
    value: 'BAG_MOVEMENT_AFTER_HOURS',
    label: 'Bag Movement After Hours',
    fields: [
      { key: 'start_time', label: 'Start time (HH:MM)', type: 'text', placeholder: '20:00' },
      { key: 'end_time', label: 'End time (HH:MM)', type: 'text', placeholder: '06:00' }
    ]
  },
  { value: 'BAG_MOVEMENT_MONITOR', label: 'Bag Movement Monitor', fields: [{ key: 'threshold_distance', label: 'Threshold distance (px)', type: 'number', placeholder: '50' }] },
  { value: 'BAG_MONITOR', label: 'Bag Monitor', fields: [{ key: 'cooldown_seconds', label: 'Cooldown (sec)', type: 'number', placeholder: '60' }] },
  {
    value: 'BAG_ODD_HOURS',
    label: 'Bag Odd Hours',
    fields: [
      { key: 'start_local', label: 'Start (HH:MM)', type: 'text', placeholder: '20:00' },
      { key: 'end_local', label: 'End (HH:MM)', type: 'text', placeholder: '06:00' },
      { key: 'cooldown_seconds', label: 'Cooldown (sec)', type: 'number', placeholder: '60' }
    ]
  },
  {
    value: 'BAG_UNPLANNED',
    label: 'Bag Unplanned',
    fields: [
      { key: 'require_active_dispatch_plan', label: 'Require active dispatch plan', type: 'checkbox' },
      { key: 'cooldown_seconds', label: 'Cooldown (sec)', type: 'number', placeholder: '60' }
    ]
  },
  {
    value: 'BAG_TALLY_MISMATCH',
    label: 'Bag Tally Mismatch',
    fields: [
      { key: 'allowed_overage_percent', label: 'Allowed overage (%)', type: 'number', placeholder: '10' },
      { key: 'cooldown_seconds', label: 'Cooldown (sec)', type: 'number', placeholder: '120' }
    ]
  },
  { value: 'ANPR_MONITOR', label: 'ANPR Monitor', fields: [] },
  { value: 'ANPR_WHITELIST_ONLY', label: 'ANPR Whitelist', fields: [{ key: 'allowed_plates', label: 'Allowed plates (comma separated)', type: 'list' }] },
  { value: 'ANPR_BLACKLIST_ALERT', label: 'ANPR Blacklist', fields: [{ key: 'blocked_plates', label: 'Blocked plates (comma separated)', type: 'list' }] }
];

function parseList(value: string) {
  return value
    .split(',')
    .map((v) => v.trim())
    .filter(Boolean);
}

function paramSummary(rule: RuleItem) {
  const parts: string[] = [];
  if (rule.start_time && rule.end_time) parts.push(`${rule.start_time}-${rule.end_time}`);
  if (rule.start && rule.end) parts.push(`${rule.start}-${rule.end}`);
  if (rule.start_local && rule.end_local) parts.push(`${rule.start_local}-${rule.end_local}`);
  if (typeof rule.threshold_seconds === 'number') parts.push(`threshold ${rule.threshold_seconds}s`);
  if (typeof rule.cooldown_seconds === 'number') parts.push(`cooldown ${rule.cooldown_seconds}s`);
  if (typeof rule.allowed_overage_percent === 'number') parts.push(`overage ${rule.allowed_overage_percent}%`);
  if (typeof rule.threshold_distance === 'number') parts.push(`distance ${rule.threshold_distance}px`);
  if (rule.allowed_plates && rule.allowed_plates.length) parts.push(`whitelist ${rule.allowed_plates.join(', ')}`);
  if (rule.blocked_plates && rule.blocked_plates.length) parts.push(`blacklist ${rule.blocked_plates.join(', ')}`);
  if (rule.require_active_dispatch_plan !== null && rule.require_active_dispatch_plan !== undefined) {
    parts.push(rule.require_active_dispatch_plan ? 'requires plan' : 'no plan required');
  }
  if (!parts.length) return '—';
  return (
    <span className="inline-flex flex-wrap items-center gap-x-2 gap-y-1">
      {parts.map((part, idx) => (
        <span key={`${part}-${idx}`} className="inline-flex items-center gap-2">
          {idx > 0 && <span className="text-slate-400">•</span>}
          <span>{part}</span>
        </span>
      ))}
    </span>
  );
}

export default function RulesPage() {
  const inlineErrorClass = 'text-xs text-red-400';
  const [rules, setRules] = useState<RuleItem[]>([]);
  const [godowns, setGodowns] = useState<GodownListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [filterGodown, setFilterGodown] = useState('');
  const [filterType, setFilterType] = useState('');
  const [filterEnabled, setFilterEnabled] = useState('');

  const [cameraOptions, setCameraOptions] = useState<string[]>([]);
  const [zoneOptions, setZoneOptions] = useState<string[]>([]);

  const [policyGodown, setPolicyGodown] = useState('');
  const [policyForm, setPolicyForm] = useState({
    timezone: 'Asia/Kolkata',
    day_start: '09:00',
    day_end: '19:00',
    presence_allowed: false,
    cooldown_seconds: '120',
    enabled: true,
    source: 'default'
  });
  const [policyLoading, setPolicyLoading] = useState(false);
  const [policySaving, setPolicySaving] = useState(false);
  const [policyError, setPolicyError] = useState<string | null>(null);

  const [form, setForm] = useState({
    id: null as number | null,
    godown_id: '',
    camera_id: '',
    zone_id: '',
    type: RULE_TYPES[0].value,
    enabled: true,
    start_time: '',
    end_time: '',
    start: '',
    end: '',
    threshold_seconds: '',
    start_local: '',
    end_local: '',
    cooldown_seconds: '',
    require_active_dispatch_plan: true,
    allowed_overage_percent: '',
    threshold_distance: '',
    allowed_plates: '',
    blocked_plates: ''
  });

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const data = await getGodowns();
        if (mounted) {
          const list = Array.isArray(data) ? data : data.items;
          setGodowns(list);
        }
      } catch {
        // ignore
      }
    })();
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    if (!policyGodown && godowns.length > 0) {
      setPolicyGodown(godowns[0].godown_id);
    }
  }, [godowns, policyGodown]);

  useEffect(() => {
    if (filterGodown && filterGodown !== policyGodown) {
      setPolicyGodown(filterGodown);
    }
  }, [filterGodown, policyGodown]);

  useEffect(() => {
    let mounted = true;
    if (!policyGodown) return;
    (async () => {
      setPolicyLoading(true);
      setPolicyError(null);
      try {
        const policy = await getAfterHoursPolicy(policyGodown);
        if (!mounted) return;
        setPolicyForm({
          timezone: policy.timezone,
          day_start: policy.day_start,
          day_end: policy.day_end,
          presence_allowed: policy.presence_allowed,
          cooldown_seconds: String(policy.cooldown_seconds ?? '120'),
          enabled: policy.enabled,
          source: policy.source ?? 'override'
        });
      } catch (e) {
        if (mounted) setPolicyError('Unable to load the policy right now; please retry.');
      } finally {
        if (mounted) setPolicyLoading(false);
      }
    })();
    return () => {
      mounted = false;
    };
  }, [policyGodown]);

  useEffect(() => {
    let mounted = true;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const resp = await getRules({
          godown_id: filterGodown || undefined,
          type: filterType || undefined,
          enabled: filterEnabled ? filterEnabled === 'true' : undefined
        });
        if (mounted) setRules(resp.items ?? []);
      } catch (e) {
        if (mounted) setError('Check your network or refresh the page to load rules.');
      } finally {
        if (mounted) setLoading(false);
      }
    })();
    return () => {
      mounted = false;
    };
  }, [filterGodown, filterType, filterEnabled]);

  useEffect(() => {
    let mounted = true;
    if (!form.godown_id) {
      setCameraOptions([]);
      return;
    }
    (async () => {
      try {
        const detail = await getGodownDetail(form.godown_id);
        if (!mounted) return;
        const cams = (detail.cameras ?? []).map((c) => c.camera_id);
        setCameraOptions(cams);
      } catch {
        if (mounted) setCameraOptions([]);
      }
    })();
    return () => {
      mounted = false;
    };
  }, [form.godown_id]);

  useEffect(() => {
    let mounted = true;
    if (!form.camera_id) {
      setZoneOptions([]);
      return;
    }
    (async () => {
      try {
        const zones = await getCameraZones(form.camera_id, form.godown_id);
        if (!mounted) return;
        const zoneIds = zones.zones.map((z) => z.id);
        setZoneOptions(zoneIds);
      } catch {
        if (mounted) setZoneOptions([]);
      }
    })();
    return () => {
      mounted = false;
    };
  }, [form.camera_id]);

  const godownOptions = useMemo(() => {
    const options = godowns.map((g) => ({
      label: `${g.name ?? g.godown_id} (${g.godown_id})`,
      value: g.godown_id
    }));
    return [{ label: 'All godowns', value: '' }, ...options];
  }, [godowns]);

  const ruleTypeOptions = useMemo(() => {
    return [{ label: 'All rule types', value: '' }, ...RULE_TYPES.map((r) => ({ label: r.label, value: r.value }))];
  }, []);

  const formType = RULE_TYPES.find((r) => r.value === form.type) ?? RULE_TYPES[0];

  async function savePolicy() {
    if (!policyGodown) return;
    setPolicySaving(true);
    setPolicyError(null);
    const cooldown = Number(policyForm.cooldown_seconds);
    const payload: Partial<AfterHoursPolicy> = {
      timezone: policyForm.timezone,
      day_start: policyForm.day_start,
      day_end: policyForm.day_end,
      presence_allowed: policyForm.presence_allowed,
      cooldown_seconds: Number.isNaN(cooldown) ? 120 : cooldown,
      enabled: policyForm.enabled
    };
    try {
      const updated = await updateAfterHoursPolicy(policyGodown, payload);
      setPolicyForm({
        timezone: updated.timezone,
        day_start: updated.day_start,
        day_end: updated.day_end,
        presence_allowed: updated.presence_allowed,
        cooldown_seconds: String(updated.cooldown_seconds ?? '120'),
        enabled: updated.enabled,
        source: updated.source ?? 'override'
      });
    } catch (e) {
      setPolicyError('Unable to save the policy; please verify your entries and try again.');
    } finally {
      setPolicySaving(false);
    }
  }

  async function refresh() {
    const resp = await getRules({
      godown_id: filterGodown || undefined,
      type: filterType || undefined,
      enabled: filterEnabled ? filterEnabled === 'true' : undefined
    });
    setRules(resp.items ?? []);
  }

  function resetForm() {
    setForm({
      id: null,
      godown_id: '',
      camera_id: '',
      zone_id: '',
      type: RULE_TYPES[0].value,
      enabled: true,
      start_time: '',
      end_time: '',
      start: '',
      end: '',
      threshold_seconds: '',
      start_local: '',
      end_local: '',
      cooldown_seconds: '',
      require_active_dispatch_plan: true,
      allowed_overage_percent: '',
      threshold_distance: '',
      allowed_plates: '',
      blocked_plates: ''
    });
  }

  async function handleSubmit() {
    if (!form.godown_id || !form.camera_id || !form.zone_id) {
      setError('Godown, camera, and zone are required.');
      return;
    }
    setError(null);
    const payload: Record<string, any> = {
      godown_id: form.godown_id,
      camera_id: form.camera_id,
      zone_id: form.zone_id,
      type: form.type,
      enabled: form.enabled
    };
    const applyNumber = (key: string, value: string) => {
      if (value === '') return;
      const num = Number(value);
      if (!Number.isNaN(num)) payload[key] = num;
    };
    if (form.start_time) payload.start_time = form.start_time;
    if (form.end_time) payload.end_time = form.end_time;
    if (form.start) payload.start = form.start;
    if (form.end) payload.end = form.end;
    if (form.start_local) payload.start_local = form.start_local;
    if (form.end_local) payload.end_local = form.end_local;
    applyNumber('threshold_seconds', form.threshold_seconds);
    applyNumber('cooldown_seconds', form.cooldown_seconds);
    applyNumber('allowed_overage_percent', form.allowed_overage_percent);
    applyNumber('threshold_distance', form.threshold_distance);
    if (form.type === 'BAG_UNPLANNED') payload.require_active_dispatch_plan = form.require_active_dispatch_plan;
    if (form.type === 'ANPR_WHITELIST_ONLY') payload.allowed_plates = parseList(form.allowed_plates);
    if (form.type === 'ANPR_BLACKLIST_ALERT') payload.blocked_plates = parseList(form.blocked_plates);

    try {
      if (form.id) {
        await updateRule(form.id, payload);
      } else {
        await createRule(payload as any);
      }
      resetForm();
      await refresh();
    } catch (e) {
      setError('Failed to save the rule; please double-check the inputs and try again.');
    }
  }

  function handleEdit(rule: RuleItem) {
    setForm({
      id: rule.id,
      godown_id: rule.godown_id,
      camera_id: rule.camera_id,
      zone_id: rule.zone_id,
      type: rule.type,
      enabled: rule.enabled,
      start_time: rule.start_time ?? '',
      end_time: rule.end_time ?? '',
      start: rule.start ?? '',
      end: rule.end ?? '',
      threshold_seconds: rule.threshold_seconds?.toString() ?? '',
      start_local: rule.start_local ?? '',
      end_local: rule.end_local ?? '',
      cooldown_seconds: rule.cooldown_seconds?.toString() ?? '',
      require_active_dispatch_plan: rule.require_active_dispatch_plan ?? true,
      allowed_overage_percent: rule.allowed_overage_percent?.toString() ?? '',
      threshold_distance: rule.threshold_distance?.toString() ?? '',
      allowed_plates: rule.allowed_plates?.join(', ') ?? '',
      blocked_plates: rule.blocked_plates?.join(', ') ?? ''
    });
  }

  async function handleToggle(rule: RuleItem) {
    const updatedEnabled = !rule.enabled;
    setRules((current) =>
      current.map((item) => (item.id === rule.id ? { ...item, enabled: updatedEnabled } : item))
    );
    try {
      setError(null);
      await updateRule(rule.id, { enabled: updatedEnabled });
      await refresh();
    } catch (e) {
      setRules((current) =>
        current.map((item) => (item.id === rule.id ? { ...item, enabled: rule.enabled } : item))
      );
      setError('Unable to update the rule status; please retry.');
    }
  }

  async function handleDelete(rule: RuleItem) {
    try {
      await deleteRule(rule.id);
      await refresh();
    } catch (e) {
      setError('Unable to delete the rule right now; please try again.');
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="space-y-2">
          <div className="hud-pill">
            <span className="pulse-dot pulse-warning" />
            Rules live
          </div>
          <div className="text-4xl font-semibold font-display tracking-tight text-slate-100 drop-shadow">
            Rule Control Center
          </div>
          <div className="text-sm text-slate-300">Create, edit, and deploy detection rules without touching YAML.</div>
        </div>
        <div className="intel-banner">Edge sync enabled</div>
      </div>

      <Card className="animate-fade-up hud-card">
        <CardHeader>
          <div className="text-lg font-semibold font-display">Filters</div>
          <div className="text-sm text-slate-600">Scope rules by godown or rule type.</div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div>
              <div className="text-xs text-slate-600 mb-1">Godown</div>
              <Select value={filterGodown} onChange={(e) => setFilterGodown(e.target.value)} options={godownOptions} />
            </div>
            <div>
              <div className="text-xs text-slate-600 mb-1">Rule type</div>
              <Select value={filterType} onChange={(e) => setFilterType(e.target.value)} options={ruleTypeOptions} />
            </div>
            <div>
              <div className="text-xs text-slate-600 mb-1">Status</div>
              <Select
                value={filterEnabled}
                onChange={(e) => setFilterEnabled(e.target.value)}
                options={[
                  { label: 'All', value: '' },
                  { label: 'Enabled', value: 'true' },
                  { label: 'Disabled', value: 'false' }
                ]}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      <Card className="animate-fade-up hud-card">
        <CardHeader>
          <div className="text-lg font-semibold font-display">After-hours policy</div>
          <div className="text-sm text-slate-600">Backend source-of-truth for after-hours presence.</div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
            <div>
              <div className="text-xs text-slate-600 mb-1">Godown</div>
              <Select
                value={policyGodown}
                onChange={(e) => setPolicyGodown(e.target.value)}
                options={[{ label: 'Select godown', value: '' }, ...godownOptions.filter((o) => o.value)]}
              />
            </div>
            <div>
              <div className="text-xs text-slate-600 mb-1">Timezone</div>
              <Input
                value={policyForm.timezone}
                onChange={(e) => setPolicyForm((s) => ({ ...s, timezone: e.target.value }))}
                placeholder="Asia/Kolkata"
              />
            </div>
            <div>
              <div className="text-xs text-slate-600 mb-1">Day start</div>
              <Input
                value={policyForm.day_start}
                onChange={(e) => setPolicyForm((s) => ({ ...s, day_start: e.target.value }))}
                placeholder="09:00"
              />
            </div>
            <div>
              <div className="text-xs text-slate-600 mb-1">Day end</div>
              <Input
                value={policyForm.day_end}
                onChange={(e) => setPolicyForm((s) => ({ ...s, day_end: e.target.value }))}
                placeholder="19:00"
              />
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3 mt-4">
            <div>
              <div className="text-xs text-slate-600 mb-1">Cooldown (sec)</div>
              <Input
                type="number"
                value={policyForm.cooldown_seconds}
                onChange={(e) => setPolicyForm((s) => ({ ...s, cooldown_seconds: e.target.value }))}
                placeholder="120"
              />
            </div>
            <div className="flex items-end gap-3">
              <label className="flex items-center gap-2 text-sm text-slate-600">
                <input
                  type="checkbox"
                  checked={policyForm.enabled}
                  onChange={(e) => setPolicyForm((s) => ({ ...s, enabled: e.target.checked }))}
                />
                Policy enabled
              </label>
              <label className="flex items-center gap-2 text-sm text-slate-600">
                <input
                  type="checkbox"
                  checked={policyForm.presence_allowed}
                  onChange={(e) => setPolicyForm((s) => ({ ...s, presence_allowed: e.target.checked }))}
                />
                Allow after-hours presence
              </label>
            </div>
            <div className="flex items-end">
              <Button onClick={savePolicy} disabled={!policyGodown || policySaving || policyLoading}>
                {policySaving ? 'Saving...' : 'Save policy'}
              </Button>
            </div>
            <div className="flex items-end text-xs text-slate-500">
              Source: {policyForm.source}
            </div>
          </div>
          {policyError && (
            <div className="mt-3">
              <p className={inlineErrorClass}>{policyError}</p>
            </div>
          )}
        </CardContent>
      </Card>

      <Card className="animate-fade-up hud-card">
        <CardHeader>
          <div className="text-lg font-semibold font-display">{form.id ? 'Edit rule' : 'Create new rule'}</div>
          <div className="text-sm text-slate-600">Rules are pushed to edge automatically within seconds.</div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
            <div>
              <div className="text-xs text-slate-600 mb-1">Godown</div>
              <Select
                value={form.godown_id}
                onChange={(e) => setForm((s) => ({ ...s, godown_id: e.target.value }))}
                options={[{ label: 'Select godown', value: '' }, ...godownOptions.filter((o) => o.value)]}
              />
            </div>
            <div>
              <div className="text-xs text-slate-600 mb-1">Camera</div>
              {cameraOptions.length ? (
                <Select
                  value={form.camera_id}
                  onChange={(e) => setForm((s) => ({ ...s, camera_id: e.target.value }))}
                  options={[{ label: 'Select camera', value: '' }, ...cameraOptions.map((c) => ({ label: c, value: c }))]}
                />
              ) : (
                <Input value={form.camera_id} onChange={(e) => setForm((s) => ({ ...s, camera_id: e.target.value }))} placeholder="CAM_GATE_1" />
              )}
            </div>
            <div>
              <div className="text-xs text-slate-600 mb-1">Zone</div>
              {zoneOptions.length ? (
                <Select
                  value={form.zone_id}
                  onChange={(e) => setForm((s) => ({ ...s, zone_id: e.target.value }))}
                  options={[{ label: 'Select zone', value: '' }, ...zoneOptions.map((z) => ({ label: z, value: z }))]}
                />
              ) : (
                <Input value={form.zone_id} onChange={(e) => setForm((s) => ({ ...s, zone_id: e.target.value }))} placeholder="all / aisle_zone3" />
              )}
            </div>
            <div>
              <div className="text-xs text-slate-600 mb-1">Rule type</div>
              <Select
                value={form.type}
                onChange={(e) => setForm((s) => ({ ...s, type: e.target.value }))}
                options={RULE_TYPES.map((r) => ({ label: r.label, value: r.value }))}
              />
            </div>
          </div>

          {formType.fields.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mt-4">
              {formType.fields.map((field) => {
                if (field.type === 'checkbox') {
                  return (
                    <label key={field.key} className="flex items-center gap-2 text-sm text-slate-700 mt-6">
                      <input
                        type="checkbox"
                        checked={Boolean((form as any)[field.key])}
                        onChange={(e) => setForm((s) => ({ ...s, [field.key]: e.target.checked }))}
                      />
                      {field.label}
                    </label>
                  );
                }
                return (
                  <div key={field.key}>
                    <div className="text-xs text-slate-600 mb-1">{field.label}</div>
                    <Input
                      type={field.type === 'number' ? 'number' : 'text'}
                      value={(form as any)[field.key] as string}
                      onChange={(e) => setForm((s) => ({ ...s, [field.key]: e.target.value }))}
                      placeholder={field.placeholder}
                    />
                  </div>
                );
              })}
            </div>
          )}

          <div className="flex items-center gap-3 mt-5">
            <Button onClick={handleSubmit}>{form.id ? 'Update rule' : 'Create rule'}</Button>
            <Button variant="outline" onClick={resetForm}>Reset</Button>
            <label className="flex items-center gap-2 text-sm text-slate-600">
              <input
                type="checkbox"
                checked={form.enabled}
                onChange={(e) => setForm((s) => ({ ...s, enabled: e.target.checked }))}
              />
              Enabled
            </label>
          </div>
        </CardContent>
      </Card>

      {error && (
        <div className="mt-4">
          <p className={inlineErrorClass}>{error}</p>
        </div>
      )}

      <Card className="animate-fade-up hud-card">
        <CardHeader>
          <div className="text-lg font-semibold font-display">Active rules</div>
          <div className="text-sm text-slate-600">Rules are synced to edge nodes automatically.</div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="text-sm text-slate-600">Loading…</div>
          ) : (
            <div className="table-shell overflow-auto">
              <Table>
                <THead>
                  <TR>
                    <TH>ID</TH>
                    <TH>Scope</TH>
                    <TH>Type</TH>
                    <TH>Params</TH>
                    <TH>Status</TH>
                    <TH>Updated</TH>
                    <TH className="text-right">Actions</TH>
                  </TR>
                </THead>
                <TBody>
                  {rules.map((rule) => (
                    <TR key={rule.id}>
                      <TD className="font-medium">#{rule.id}</TD>
                      <TD>
                        <div>{rule.godown_id}</div>
                        <div className="text-xs text-slate-500 flex flex-wrap items-center gap-2">
                          <span>{rule.camera_id}</span>
                          <span className="text-slate-400">•</span>
                          <span>{rule.zone_id}</span>
                        </div>
                      </TD>
                      <TD>{rule.type.replaceAll('_', ' ')}</TD>
                      <TD className="text-xs text-slate-500">{paramSummary(rule)}</TD>
                      <TD>
                        <Badge variant="outline" className={rule.enabled ? 'text-emerald-700 border-emerald-200' : 'text-slate-500 border-slate-200'}>
                          {rule.enabled ? 'Enabled' : 'Disabled'}
                        </Badge>
                      </TD>
                      <TD>{formatUtc(rule.updated_at ?? rule.created_at ?? '')}</TD>
                      <TD className="text-right space-x-2">
                        <Button variant="outline" onClick={() => handleEdit(rule)}>Edit</Button>
                        <Button variant="ghost" onClick={() => handleToggle(rule)}>
                          {rule.enabled ? 'Disable' : 'Enable'}
                        </Button>
                        <Button variant="danger" onClick={() => handleDelete(rule)}>Delete</Button>
                      </TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
