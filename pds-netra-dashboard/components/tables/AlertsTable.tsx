import Link from 'next/link';
import { Table, THead, TBody, TR, TH, TD } from '../ui/table';
import { Badge } from '../ui/badge';
import type { AlertItem } from '@/lib/types';
import { formatUtc, humanAlertType, severityBadgeClass } from '@/lib/formatters';

export function AlertsTable({ alerts }: { alerts: AlertItem[] }) {
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
            <TH>Alert</TH>
            <TH>Severity</TH>
            <TH>Godown</TH>
            <TH>Zone</TH>
            <TH>Start</TH>
            <TH>Status</TH>
            <TH className="text-right">Events</TH>
          </TR>
        </THead>
        <TBody>
          {alerts.map((a) => (
            <TR key={a.id}>
              <TD>
                <span className="font-medium text-slate-200">
                  {humanAlertType(a.alert_type)}
                </span>
                {a.alert_type === 'BLACKLIST_PERSON_MATCH' && (a.key_meta?.person_name || a.key_meta?.person_id) ? (
                  <div className="text-xs text-slate-500 mt-1">
                    Blacklisted: {a.key_meta?.person_name ?? 'Unknown'}
                    {formatScore(a.key_meta?.match_score) ? ` | Match ${formatScore(a.key_meta?.match_score)}` : ''}
                  </div>
                ) : null}
                {a.key_meta?.reason ? (
                  <div className="text-xs text-slate-500 mt-1">Reason: {a.key_meta.reason}</div>
                ) : null}
                {a.summary ? <div className="text-xs text-slate-500 mt-1">{a.summary}</div> : null}
              </TD>
              <TD>
                <Badge className={severityBadgeClass(a.severity_final)}>
                  {a.severity_final.toUpperCase()}
                </Badge>
              </TD>
              <TD>{a.godown_name ?? a.godown_id}</TD>
              <TD>{a.key_meta?.zone_id ?? '-'}</TD>
              <TD>{formatUtc(a.start_time)}</TD>
              <TD>
                <Badge variant="outline">{a.status}</Badge>
              </TD>
              <TD className="text-right">{a.count_events ?? '-'}</TD>
            </TR>
          ))}
        </TBody>
      </Table>
    </div>
  );
}
