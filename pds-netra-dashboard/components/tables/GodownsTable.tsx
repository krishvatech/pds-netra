import Link from 'next/link';
import { Table, THead, TBody, TR, TH, TD } from '../ui/table';
import { Badge } from '../ui/badge';
import type { GodownListItem } from '@/lib/types';
import { formatUtc } from '@/lib/formatters';

function statusLabel(status: GodownListItem['status']) {
  if (status === 'CRITICAL') return <Badge className="bg-red-100 text-red-800 border-red-200">Critical</Badge>;
  if (status === 'ISSUES') return <Badge className="bg-yellow-100 text-yellow-800 border-yellow-200">Issues</Badge>;
  return <Badge className="bg-green-100 text-green-800 border-green-200">OK</Badge>;
}

export function GodownsTable({ items }: { items: GodownListItem[] }) {
  return (
    <div className="table-shell overflow-auto">
      <Table>
        <THead>
          <TR>
            <TH>Godown</TH>
            <TH>District</TH>
            <TH>Cameras</TH>
            <TH>Open alerts</TH>
            <TH>Last event</TH>
            <TH>Status</TH>
          </TR>
        </THead>
        <TBody>
          {items.map((g) => (
            <TR key={g.godown_id}>
              <TD>
                <Link href={`/dashboard/godowns/${encodeURIComponent(g.godown_id)}`} className="font-medium text-slate-900 hover:underline">
                  {g.name ?? g.godown_id}
                </Link>
                <div className="text-xs text-slate-500">{g.godown_id}</div>
              </TD>
              <TD>{g.district ?? '-'}</TD>
              <TD>
                {g.cameras_total ?? 0}
                {typeof g.cameras_offline === 'number' && g.cameras_offline > 0 ? (
                  <span className="ml-2 text-xs text-red-700">({g.cameras_offline} offline)</span>
                ) : null}
              </TD>
              <TD>
                <span className="text-xs">Critical: {g.open_alerts_critical ?? 0}</span>
                <span className="ml-3 text-xs">Warning: {g.open_alerts_warning ?? 0}</span>
              </TD>
              <TD>{formatUtc(g.last_event_time_utc ?? null)}</TD>
              <TD>{statusLabel(g.status ?? 'OK')}</TD>
            </TR>
          ))}
        </TBody>
      </Table>
    </div>
  );
}
