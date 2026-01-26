import { Table, THead, TBody, TR, TH, TD } from '../ui/table';
import { Badge } from '../ui/badge';
import type { EventItem } from '@/lib/types';
import { formatUtc } from '@/lib/formatters';

function movementLabel(value?: string | null) {
  if (!value) return 'UNKNOWN';
  return value.replaceAll('_', ' ');
}

function getExtraValue(meta: EventItem['meta'], key: string): string | null {
  const extra = meta?.extra;
  if (!extra || typeof extra !== 'object') return null;
  const val = (extra as Record<string, unknown>)[key];
  if (val === undefined || val === null) return null;
  return String(val);
}

export function MovementEventsTable({ events }: { events: EventItem[] }) {
  return (
    <div className="table-shell overflow-auto">
      <Table>
        <THead>
          <TR>
            <TH>Time</TH>
            <TH>Godown</TH>
            <TH>Camera</TH>
            <TH>Zone</TH>
            <TH>Movement</TH>
            <TH>Plan</TH>
            <TH>Expected</TH>
            <TH>Observed</TH>
            <TH className="text-right">Severity</TH>
          </TR>
        </THead>
        <TBody>
          {events.map((ev) => (
            <TR key={ev.event_id}>
              <TD>{formatUtc(ev.timestamp_utc)}</TD>
              <TD>{ev.godown_id}</TD>
              <TD>{ev.camera_id}</TD>
              <TD>{ev.meta?.zone_id ?? '-'}</TD>
              <TD>{movementLabel(ev.meta?.movement_type)}</TD>
              <TD>{getExtraValue(ev.meta, 'plan_id') ?? '-'}</TD>
              <TD>{getExtraValue(ev.meta, 'expected_bag_count') ?? '-'}</TD>
              <TD>{getExtraValue(ev.meta, 'observed_bag_count') ?? '-'}</TD>
              <TD className="text-right">
                <Badge variant="outline">{ev.severity?.toUpperCase?.() ?? ev.severity}</Badge>
              </TD>
            </TR>
          ))}
        </TBody>
      </Table>
    </div>
  );
}
