// app/dashboard/alerts/[alertId]/page.tsx
"use client";

import React, { useEffect, useMemo, useState } from "react";
import { Select } from "@/components/ui/select";

type AlertDetail = {
  id: string;
  alert_type: string;
  severity_final: string;
  status: string;
  start_time: string;
  end_time: string | null;
  summary?: string | null;
  title?: string | null;

  godown_id: string;
  district?: string | null;

  // backend may send this as key_meta (your code already uses it)
  key_meta?: Record<string, any> | null;
};

type DeliveryRow = {
  id: string;
  channel: string;
  target: string;
  status: string;
  attempts: number;
  sent_at?: string | null;
  last_error?: string | null;
};

type TimelineItem = {
  type: string;
  label: string;
  ts: string;
  meta?: string | null;
};

function formatUtc(ts: string | null | undefined) {
  if (!ts) return "—";
  try {
    const d = new Date(ts);
    if (Number.isNaN(d.getTime())) return String(ts);
    return d.toISOString().replace("T", " ").replace("Z", " UTC");
  } catch {
    return String(ts);
  }
}

function humanAlertType(alertType: string) {
  const map: Record<string, string> = {
    ANIMAL_INTRUSION: "Animal Intrusion",
    FIRE_DETECTED: "Fire Detected",
    CAMERA_HEALTH_ISSUE: "Camera Health Issue",
    SECURITY_UNAUTH_ACCESS: "Unauthorized Access",
    AFTER_HOURS_PERSON_PRESENCE: "After-hours Person Presence",
    AFTER_HOURS_VEHICLE_PRESENCE: "After-hours Vehicle Presence",
    ANPR_MISMATCH_VEHICLE: "ANPR Mismatch",
    ANPR_PLATE_NOT_VERIFIED: "Not Verified Plate Detected",
    ANPR_PLATE_BLACKLIST: "Blacklisted Plate Detected",
    ANPR_PLATE_ALERT: "ANPR Plate Alert",
  };
  return map[alertType] ?? alertType.replaceAll("_", " ");
}

function severityBadgeClass(sev: string) {
  const s = (sev || "").toLowerCase();
  if (s === "critical") return "inline-flex rounded-full px-2 py-1 text-xs font-semibold bg-red-500/20 text-red-200";
  if (s === "warning") return "inline-flex rounded-full px-2 py-1 text-xs font-semibold bg-amber-500/20 text-amber-200";
  return "inline-flex rounded-full px-2 py-1 text-xs font-semibold bg-slate-500/20 text-slate-200";
}

function ErrorBanner({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200 flex items-center justify-between gap-3">
      <div>{message}</div>
      {onRetry && (
        <button
          onClick={onRetry}
          className="rounded-lg border border-red-300/30 bg-red-400/10 px-3 py-1 text-xs hover:bg-red-400/20"
        >
          Retry
        </button>
      )}
    </div>
  );
}

function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <div className={`rounded-2xl border border-white/10 bg-white/5 ${className}`}>{children}</div>;
}
function CardHeader({ children }: { children: React.ReactNode }) {
  return <div className="p-4 border-b border-white/10">{children}</div>;
}
function CardContent({ children }: { children: React.ReactNode }) {
  return <div className="p-4">{children}</div>;
}
function Badge({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <span className={className}>{children}</span>;
}
function Button({ children, onClick }: { children: React.ReactNode; onClick?: () => void }) {
  return (
    <button
      onClick={onClick}
      className="rounded-xl bg-white/10 hover:bg-white/15 border border-white/10 px-4 py-2 text-sm text-slate-100"
    >
      {children}
    </button>
  );
}
function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={`w-full rounded-xl bg-black/20 border border-white/10 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 outline-none focus:border-white/20 ${
        props.className ?? ""
      }`}
    />
  );
}
export default function AlertDetailPage({ params }: { params: { alertId: string } }) {
  const alertId = params.alertId;

  const [detail, setDetail] = useState<AlertDetail | null>(null);
  const [deliveries, setDeliveries] = useState<DeliveryRow[]>([]);
  const [timeline, setTimeline] = useState<TimelineItem[]>([]);
  const [error, setError] = useState<string>("");

  const [actionType, setActionType] = useState<string>("ACK");
  const [note, setNote] = useState<string>("");

  // ✅ IMPORTANT: adjust these if your backend routes differ
  const API_BASE = ""; // keep empty if dashboard proxy is set; otherwise set like "http://127.0.0.1:8001"
  const detailUrl = `${API_BASE}/api/v1/alerts/${encodeURIComponent(alertId)}`;
  const deliveriesUrl = `${API_BASE}/api/v1/alerts/${encodeURIComponent(alertId)}/deliveries`;
  const timelineUrl = `${API_BASE}/api/v1/alerts/${encodeURIComponent(alertId)}/timeline`;
  const actionUrl = `${API_BASE}/api/v1/alerts/${encodeURIComponent(alertId)}/actions`;

  useEffect(() => {
    let alive = true;

    async function load() {
      setError("");
      try {
        const r = await fetch(detailUrl, { cache: "no-store" });
        if (!r.ok) throw new Error(`Failed to load alert: ${r.status}`);
        const data = (await r.json()) as AlertDetail;
        if (!alive) return;
        setDetail(data);
      } catch (e: any) {
        if (!alive) return;
        setError(e?.message || "Failed to load alert");
      }

      // optional loads (don’t fail the page if these endpoints don’t exist)
      try {
        const r = await fetch(deliveriesUrl, { cache: "no-store" });
        if (r.ok) setDeliveries((await r.json()) as DeliveryRow[]);
      } catch {}
      try {
        const r = await fetch(timelineUrl, { cache: "no-store" });
        if (r.ok) setTimeline((await r.json()) as TimelineItem[]);
      } catch {}
    }

    load();
    return () => {
      alive = false;
    };
  }, [detailUrl, deliveriesUrl, timelineUrl]);

  const keyMetaEntries = useMemo(() => {
    const km = detail?.key_meta ?? null;
    if (!km || typeof km !== "object") return [];
    // ✅ Ensure animal class is visible clearly
    // common keys from your backend: animal_species, movement_type, species, animal_count, snapshot_url
    const preferredOrder = [
      "animal_species",
      "movement_type",
      "species",
      "animal_count",
      "count",
      "animal_confidence",
      "confidence",
      "animal_is_night",
      "zone_id",
      "snapshot_url",
      "clip_url",
      "vehicle_plate",
      "plate_text",
    ];

    const entries = Object.entries(km).filter(([k]) => k !== "__proto__");
    entries.sort((a, b) => {
      const ai = preferredOrder.indexOf(a[0]);
      const bi = preferredOrder.indexOf(b[0]);
      const aRank = ai === -1 ? 999 : ai;
      const bRank = bi === -1 ? 999 : bi;
      if (aRank !== bRank) return aRank - bRank;
      return a[0].localeCompare(b[0]);
    });
    return entries;
  }, [detail?.key_meta]);

  async function submitAction() {
    try {
      // if your backend doesn't have this endpoint yet, this will just show an error
      const r = await fetch(actionUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: actionType, note }),
      });
      if (!r.ok) throw new Error(`Failed to log action: ${r.status}`);
      // reload timeline after action
      try {
        const t = await fetch(timelineUrl, { cache: "no-store" });
        if (t.ok) setTimeline((await t.json()) as TimelineItem[]);
      } catch {}
      setNote("");
    } catch (e: any) {
      setError(e?.message || "Failed to log action");
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="space-y-2">
          <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-200">
            <span className="inline-block h-2 w-2 rounded-full bg-amber-400" />
            Incident file
          </div>

          <div className="text-4xl font-semibold tracking-tight text-slate-100 drop-shadow">Alert Detail</div>
          <div className="text-sm text-slate-300">Review the full timeline and context for this alert.</div>
        </div>

        <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-2 text-sm text-slate-200">Case view</div>
      </div>

      <Card className="animate-fade-up">
        <CardHeader>
          <div className="text-lg font-semibold text-slate-100">Incident summary</div>
        </CardHeader>

        <CardContent>
          {error && <ErrorBanner message={error} onRetry={() => window.location.reload()} />}
          {!detail && !error && <div className="text-sm text-slate-400">Loading…</div>}

          {/* ✅ FIXED: clean JSX structure, properly closed blocks */}
          {detail && (
            <>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
                <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
                  <div className="text-xs text-slate-400 uppercase tracking-[0.3em]">Type</div>
                  <div className="mt-1 font-semibold text-slate-100">{humanAlertType(detail.alert_type)}</div>

                  {/* ✅ Show animal class clearly at top for intrusion alerts */}
                  {detail.alert_type === "ANIMAL_INTRUSION" && (
  <div className="text-xs text-slate-400">
    Detected:{" "}
    <span className="font-semibold text-slate-100">
      {String(
        detail.key_meta?.animal_label ??
          detail.key_meta?.animal_species ??
          "unknown"
      )}
    </span>
  </div>
)}

                </div>
                <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
                  <div className="text-xs text-slate-400 uppercase tracking-[0.3em]">Severity</div>
                  <div className="mt-2">
                    <Badge className={severityBadgeClass(detail.severity_final)}>{detail.severity_final.toUpperCase()}</Badge>
                  </div>
                </div>

                <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
                  <div className="text-xs text-slate-400 uppercase tracking-[0.3em]">Status</div>
                  <div className="mt-1 font-semibold text-slate-100">{detail.status}</div>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4">
                <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
                  <div className="text-xs text-slate-400 uppercase tracking-[0.3em]">Godown</div>
                  <div className="font-semibold text-slate-100">{detail.godown_id}</div>
                  {detail.district && <div className="text-sm text-slate-400">{detail.district}</div>}
                </div>

                <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
                  <div className="text-xs text-slate-400 uppercase tracking-[0.3em]">Time window</div>
                  <div className="text-sm text-slate-200">
                    <span className="font-medium">Start:</span> {formatUtc(detail.start_time)}
                  </div>
                  <div className="text-sm text-slate-200">
                    <span className="font-medium">End:</span> {formatUtc(detail.end_time)}
                  </div>
                </div>
              </div>

              {detail.summary && (
                <div className="rounded-2xl border border-white/10 bg-black/20 p-4 mb-4">
                  <div className="text-xs text-slate-400 uppercase tracking-[0.3em]">Summary</div>
                  <div className="mt-1 text-slate-100">{detail.summary}</div>
                </div>
              )}

              {detail.key_meta?.snapshot_url && (
                <div className="rounded-2xl border border-white/10 bg-black/20 p-4 mb-4">
                  <div className="text-xs text-slate-400 uppercase tracking-[0.3em]">Evidence Snapshot</div>
                  <a
                    href={String(detail.key_meta.snapshot_url)}
                    target="_blank"
                    rel="noreferrer"
                    className="text-amber-300 hover:underline"
                  >
                    Open snapshot
                  </a>
                </div>
              )}

              <div className="rounded-2xl border border-white/10 bg-black/20 p-4 mb-4">
                <div className="text-xs text-slate-400 uppercase tracking-[0.3em] mb-2">Delivery status</div>
                {deliveries.length === 0 ? (
                  <div className="text-sm text-slate-400">No delivery records yet.</div>
                ) : (
                  <div className="overflow-auto rounded-xl border border-white/10">
                    <table className="min-w-[720px] text-sm">
                      <thead>
                        <tr className="text-left text-slate-400">
                          <th className="py-2 px-3">Channel</th>
                          <th className="py-2 px-3">Target</th>
                          <th className="py-2 px-3">Status</th>
                          <th className="py-2 px-3">Attempts</th>
                          <th className="py-2 px-3">Sent at</th>
                          <th className="py-2 px-3">Last error</th>
                        </tr>
                      </thead>
                      <tbody>
                        {deliveries.map((d) => (
                          <tr key={d.id} className="border-t border-white/10">
                            <td className="py-2 px-3">{d.channel}</td>
                            <td className="py-2 px-3">{d.target}</td>
                            <td className="py-2 px-3">{d.status}</td>
                            <td className="py-2 px-3">{d.attempts}</td>
                            <td className="py-2 px-3">{formatUtc(d.sent_at ?? null)}</td>
                            <td className="py-2 px-3 text-xs text-slate-400">{d.last_error ?? "-"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

              <div className="rounded-2xl border border-white/10 bg-black/20 p-4 mb-4">
                <div className="text-xs text-slate-400 uppercase tracking-[0.3em] mb-2">Incident actions</div>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                  <div>
                    <div className="text-xs text-slate-400 mb-1">Action</div>
                    <Select
                      value={actionType}
                      onChange={(e) => setActionType(e.target.value)}
                      options={[
                        { label: "Acknowledge", value: "ACK" },
                        { label: "Assign", value: "ASSIGN" },
                        { label: "Resolve", value: "RESOLVE" },
                        { label: "Reopen", value: "REOPEN" },
                        { label: "Note", value: "NOTE" },
                      ]}
                    />
                  </div>

                  <div>
                    <div className="text-xs text-slate-400 mb-1">Note / Assignee</div>
                    <Input value={note} onChange={(e) => setNote(e.target.value)} placeholder="Optional note" />
                  </div>

                  <div className="flex items-end">
                    <Button onClick={submitAction}>Log action</Button>
                  </div>
                </div>
              </div>

              {timeline.length > 0 && (
                <div className="rounded-2xl border border-white/10 bg-black/20 p-4 mb-4">
                  <div className="text-xs text-slate-400 uppercase tracking-[0.3em] mb-2">Investigation timeline</div>
                  <div className="space-y-2">
                    {timeline.map((item, idx) => (
                      <div key={`${item.type}-${idx}`} className="flex items-center justify-between text-sm">
                        <div className="flex items-center gap-2">
                          <span className="text-xs uppercase tracking-[0.3em] text-slate-400">{item.type}</span>
                          <span className="font-medium text-slate-100">{item.label}</span>
                          {item.meta && <span className="text-xs text-slate-400">{item.meta}</span>}
                        </div>
                        <div className="text-xs text-slate-400">{formatUtc(item.ts)}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {keyMetaEntries.length > 0 && (
                <div className="rounded-2xl border border-white/10 bg-black/20 p-4 mb-1">
                  <div className="text-xs text-slate-400 mb-2">Key details</div>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                    {keyMetaEntries.map(([k, v]) => (
                      <div key={k} className="text-sm">
                        <span className="text-slate-400">{k}:</span>{" "}
                        <span className="font-medium text-slate-100">{String(v)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
