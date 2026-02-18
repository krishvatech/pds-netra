import { Table, THead, TBody, TR, TH, TD } from '../ui/table';
import { Badge } from '../ui/badge';
import { ConfirmDeletePopover } from '../ui/dialog';
import type { DispatchTraceItem } from '@/lib/types';
import { formatUtc } from '@/lib/formatters';

function formatDelay(mins?: number | null) {
  if (mins === null || mins === undefined) return '-';
  const hours = mins / 60;
  if (hours < 1) return `${mins}m`;
  return `${hours.toFixed(1)}h`;
}

export function DispatchTraceTable({
  items,
  onEdit,
  onDelete,
  deleteBusy = false
}: {
  items: DispatchTraceItem[];
  onEdit?: (item: DispatchTraceItem) => void;
  onDelete?: (item: DispatchTraceItem) => void;
  deleteBusy?: boolean;
}) {
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
            {(onEdit || onDelete) && <TH className="text-right">Actions</TH>}
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
              {(onEdit || onDelete) && (
                <TD className="text-right">
                  <div className="flex justify-end gap-2">
                    {onEdit && (
                      <button
                        onClick={() => onEdit(issue)}
                        className="p-1.5 rounded-md hover:bg-slate-800 text-slate-400 hover:text-amber-500 transition-colors"
                        title="Edit issue"
                      >
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                          <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
                        </svg>
                      </button>
                    )}
                    {onDelete && (
                      <ConfirmDeletePopover
                        title="Delete dispatch issue"
                        description={`Are you sure you want to delete issue #${issue.issue_id}? This cannot be undone.`}
                        confirmText="Delete"
                        onConfirm={() => onDelete(issue)}
                        isBusy={deleteBusy}
                      >
                        <button
                          className="p-1.5 rounded-md hover:bg-slate-800 text-slate-400 hover:text-rose-500 transition-colors"
                          title="Delete issue"
                        >
                          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <polyline points="3 6 5 6 21 6" />
                            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                            <line x1="10" y1="11" x2="10" y2="17" />
                            <line x1="14" y1="11" x2="14" y2="17" />
                          </svg>
                        </button>
                      </ConfirmDeletePopover>
                    )}
                  </div>
                </TD>
              )}
            </TR>
          ))}
        </TBody>
      </Table>
    </div>
  );
}
