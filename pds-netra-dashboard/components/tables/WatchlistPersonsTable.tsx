import Link from 'next/link';
import { Table, THead, TBody, TR, TH, TD } from '../ui/table';
import { Badge } from '../ui/badge';
import { ScrollArea } from '../ui/scroll-area';
import { RowActions } from '@/components/watchlist/RowActions';
import type { WatchlistPerson } from '@/lib/types';
import { formatUtc } from '@/lib/formatters';

type WatchlistPersonsTableProps = {
  persons: WatchlistPerson[];
  onEdit: (person: WatchlistPerson) => void;
  onDelete: (person: WatchlistPerson) => void;
};

export function WatchlistPersonsTable({ persons, onEdit, onDelete }: WatchlistPersonsTableProps) {
  return (
    <div className="rounded-xl border border-white/10 bg-slate-950/35">
      <ScrollArea className="h-[60vh]">
        <Table>
          <THead>
            <TR>
              <TH>Name</TH>
              <TH>Alias</TH>
              <TH>Reason</TH>
              <TH>Status</TH>
              <TH>Images</TH>
              <TH>Updated</TH>
              <TH className="w-[68px] text-right">Actions</TH>
            </TR>
          </THead>
          <TBody>
            {persons.map((p) => (
              <TR key={p.id} className="border-t border-white/10">
                <TD>
                  <Link href={`/dashboard/watchlist/${encodeURIComponent(p.id)}`} className="font-medium hover:underline">
                    {p.name}
                  </Link>
                  <div className="text-xs text-slate-400">{p.id}</div>
                </TD>
                <TD>{p.alias ?? '-'}</TD>
                <TD>{p.reason ?? '-'}</TD>
                <TD>
                  <Badge variant={p.status === 'ACTIVE' ? 'default' : 'outline'}>{p.status}</Badge>
                </TD>
                <TD>{p.images?.length ?? 0}</TD>
                <TD>{p.updated_at ? formatUtc(p.updated_at) : '-'}</TD>
                <TD className="text-right">
                  <RowActions name={p.name} onEdit={() => onEdit(p)} onDelete={() => onDelete(p)} />
                </TD>
              </TR>
            ))}
          </TBody>
        </Table>
      </ScrollArea>
    </div>
  );
}
