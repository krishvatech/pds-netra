import Link from 'next/link';
import { Table, THead, TBody, TR, TH, TD } from '../ui/table';
import { Badge } from '../ui/badge';
import type { EventItem } from '@/lib/types';
import { formatUtc, humanEventType, severityBadgeClass } from '@/lib/formatters';
export function EventsTable({ events, showGodown = false }: { events: EventItem[]; showGodown?: boolean }) {
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8001';
  const resolveSnapshot = (event: EventItem) => {
    const direct = event.image_url;
    const metaSnapshot =
      ((event.meta as any)?.extra?.snapshot_url as string | undefined) ??
      ((event.meta as any)?.snapshot_url as string | undefined) ??
      null;
    return resolveMediaUrl(direct || metaSnapshot || undefined);
  };
  const resolveMediaUrl = (url?: string | null) => {
    if (!url) return '';
    if (url.startsWith('http://') || url.startsWith('https://')) {
      try {
        const parsed = new URL(url);
        const host = parsed.hostname.toLowerCase();
        const internal =
          host === 'backend' ||
          host === 'localhost' ||
          host === '127.0.0.1' ||
          host === '0.0.0.0' ||
          host.startsWith('127.');
        if (internal && parsed.pathname.startsWith('/media/')) {
          return `${apiBase}${parsed.pathname}${parsed.search}`;
        }
      } catch {}
      return url;
    }
    if (url.startsWith('/media/')) return `${apiBase}${url}`;
    return url;
  };
  const formatScore = (raw?: unknown) => {
    if (raw === null || raw === undefined) return null;
    const val = typeof raw === 'number' ? raw : Number(raw);
    if (Number.isNaN(val)) return null;
    return val.toFixed(3);
  };
  return (
    <div className="table-shell overflow-auto">
      <Table>
        <THead>
          <TR>
            <TH>Time</TH>
            <TH>Event</TH>
            <TH>Severity</TH>
            {showGodown ? <TH>Godown</TH> : null}
            <TH>Camera</TH>
            <TH>Zone</TH>
            <TH>Snapshot</TH>
          </TR>
        </THead>
        <TBody>
          {events.map((e) => (
            <TR key={e.id ?? e.event_id}>
              <TD>{formatUtc(e.timestamp_utc)}</TD>
              <TD className="font-medium">
                {e.event_type === 'UNAUTH_PERSON' && e.meta?.movement_type
                  ? `Detected: ${e.meta.movement_type}`
                  : e.event_type === 'ANIMAL_INTRUSION' && (e.meta?.animal_species || e.meta?.animal_label)
                    ? `Animal Intrusion: ${e.meta?.animal_label ?? e.meta?.animal_species}`
                    : humanEventType(e.event_type)}
                {e.event_type === 'FACE_MATCH' && (e.meta?.person_name || e.meta?.person_id) ? (
                  <div className="text-xs text-slate-500 mt-1">
                    Blacklisted: {e.meta?.person_name ?? 'Unknown'}
                    {formatScore(e.meta?.match_score) ? ` | Match ${formatScore(e.meta?.match_score)}` : ''}
                  </div>
                ) : null}
                {e.event_type === 'FACE_IDENTIFIED' && (e.meta?.person_id || e.meta?.person_name) ? (
                  <div className="text-xs text-slate-500 mt-1">
                    Authorized: {e.meta.person_name ?? 'Unknown'}{e.meta.person_id ? ` (${e.meta.person_id})` : ''}
                  </div>
                ) : null}
                {e.meta?.reason ? (
                  <div className="text-xs text-slate-500 mt-1">Reason: {e.meta.reason}</div>
                ) : null}
              </TD>
              <TD>
                <Badge className={severityBadgeClass(e.severity)}>{e.severity.toUpperCase()}</Badge>
              </TD>
              {showGodown ? <TD>{e.godown_id}</TD> : null}
              <TD>{e.camera_id}</TD>
              <TD>{e.meta?.zone_id ?? '-'}</TD>
              <TD>
                {resolveSnapshot(e) ? (
                  <Link className="text-sm underline" href={resolveSnapshot(e)} target="_blank" rel="noreferrer">
                    View
                  </Link>
                ) : (
                  '-'
                )}
              </TD>
            </TR>
          ))}
        </TBody>
      </Table>
    </div>
  );
}
