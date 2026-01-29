import { Table, THead, TBody, TR, TH, TD } from '../ui/table';
import { Badge } from '../ui/badge';
import type { WatchlistMatchEvent } from '@/lib/types';
import { formatUtc } from '@/lib/formatters';

export function WatchlistMatchesTable({ matches }: { matches: WatchlistMatchEvent[] }) {
  return (
    <div className="table-shell overflow-auto">
      <Table>
        <THead>
          <TR>
            <TH>Time</TH>
            <TH>Godown</TH>
            <TH>Camera</TH>
            <TH>Score</TH>
            <TH>Evidence</TH>
          </TR>
        </THead>
        <TBody>
          {matches.map((m) => (
            <TR key={m.id}>
              <TD>{formatUtc(m.occurred_at)}</TD>
              <TD>{m.godown_id}</TD>
              <TD>{m.camera_id}</TD>
              <TD>
                <Badge>{m.match_score.toFixed(3)}</Badge>
              </TD>
              <TD>
                {m.snapshot_url ? (
                  <a href={m.snapshot_url} target="_blank" rel="noreferrer" className="text-amber-300 hover:underline">
                    Snapshot
                  </a>
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
