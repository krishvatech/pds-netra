import Link from 'next/link';
import { Table, THead, TBody, TR, TH, TD } from '../ui/table';
import { Badge } from '../ui/badge';
import type { EventItem } from '@/lib/types';
import { formatUtc, humanEventType, severityBadgeClass } from '@/lib/formatters';

export function EventsTable({ events, showGodown = false }: { events: EventItem[]; showGodown?: boolean }) {
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8001';
  const resolveMediaUrl = (url?: string | null) => {
    if (!url) return '';
    if (url.startsWith('http://') || url.startsWith('https://')) return url;
    if (url.startsWith('/media/')) return `${apiBase}${url}`;
    return url;
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
                  : humanEventType(e.event_type)}
              </TD>
              <TD>
                <Badge className={severityBadgeClass(e.severity)}>{e.severity.toUpperCase()}</Badge>
              </TD>
              {showGodown ? <TD>{e.godown_id}</TD> : null}
              <TD>{e.camera_id}</TD>
              <TD>{e.meta?.zone_id ?? '-'}</TD>
              <TD>
                {e.image_url ? (
                  <Link className="text-sm underline" href={resolveMediaUrl(e.image_url)} target="_blank" rel="noreferrer">
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
