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
export function GodownsTable({
  items,
  onEdit,
  onDelete
}: {
  items: GodownListItem[];
  onEdit?: (item: GodownListItem) => void;
  onDelete?: (id: string) => void;
}) {
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
            <TH className="text-right">Actions</TH>
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
              <TD className="text-right">
                <div className="flex justify-end gap-2">
                  <button
                    onClick={() => onEdit?.(g)}
                    className="p-1 hover:bg-slate-100 rounded text-slate-600 hover:text-blue-600 transition-colors"
                    title="Edit"
                  >
                    <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M12 20h9" />
                      <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4 12.5-12.5z" />
                    </svg>
                  </button>
                  <button
                    onClick={() => onDelete?.(g.godown_id)}
                    className="p-1 hover:bg-slate-100 rounded text-slate-600 hover:text-red-600 transition-colors"
                    title="Delete"
                  >
                    <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M3 6h18" />
                      <path d="M8 6V4h8v2" />
                      <path d="M10 11v6" />
                      <path d="M14 11v6" />
                      <path d="M6 6l1 14h10l1-14" />
                    </svg>
                  </button>
                </div>
              </TD>
            </TR>
          ))}
        </TBody>
      </Table>
    </div>
  );
}
