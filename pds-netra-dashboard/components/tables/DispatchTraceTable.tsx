import { Table, THead, TBody, TR, TH, TD } from '../ui/table';
import { Badge } from '../ui/badge';
import type { DispatchTraceItem } from '@/lib/types';
import { formatUtc } from '@/lib/formatters';

function formatDelay(mins?: number | null) {
  if (mins === null || mins === undefined) return '-';
  const hours = mins / 60;
  if (hours < 1) return `${mins}m`;
  return `${hours.toFixed(1)}h`;
}

export function DispatchTraceTable({ items }: { items: DispatchTraceItem[] }) {
  return (
    <div className="table-shell overflow-auto">
      <Table>
        <THead>
          <TR>
            <TH>Issue</TH>
            <TH>Godown</TH>
            <TH>Camera</TH>
            <TH>Zone</TH>
            <TH>Issued</TH>
            <TH>First Movement</TH>
            <TH>Delay</TH>
            <TH>SLA</TH>
            <TH>Status</TH>
            <TH className="text-right">24h Moves</TH>
          </TR>
        </THead>
        <TBody>
          {items.map((issue) => (
            <TR key={issue.issue_id}>
              <TD className="font-medium">#{issue.issue_id}</TD>
              <TD>{issue.godown_id}</TD>
              <TD>{issue.camera_id ?? '-'}</TD>
              <TD>{issue.zone_id ?? '-'}</TD>
              <TD>{formatUtc(issue.issue_time_utc)}</TD>
              <TD>{issue.first_movement_utc ? formatUtc(issue.first_movement_utc) : '-'}</TD>
              <TD>{formatDelay(issue.delay_minutes)}</TD>
              <TD>
                <Badge variant="outline" className={issue.sla_met ? 'text-emerald-700 border-emerald-200' : 'text-rose-700 border-rose-200'}>
                  {issue.sla_met ? 'Met' : 'Missed'}
                </Badge>
              </TD>
              <TD>
                <Badge variant="outline">{issue.status}</Badge>
              </TD>
              <TD className="text-right">{issue.movement_count_24h}</TD>
            </TR>
          ))}
        </TBody>
      </Table>
    </div>
  );
}
