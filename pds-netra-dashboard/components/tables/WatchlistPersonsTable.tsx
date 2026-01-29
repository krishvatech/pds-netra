import Link from 'next/link';
import { Table, THead, TBody, TR, TH, TD } from '../ui/table';
import { Badge } from '../ui/badge';
import type { WatchlistPerson } from '@/lib/types';

export function WatchlistPersonsTable({ persons }: { persons: WatchlistPerson[] }) {
  return (
    <div className="table-shell overflow-auto">
      <Table>
        <THead>
          <TR>
            <TH>Name</TH>
            <TH>Alias</TH>
            <TH>Reason</TH>
            <TH>Status</TH>
            <TH>Images</TH>
            <TH>Updated</TH>
          </TR>
        </THead>
        <TBody>
          {persons.map((p) => (
            <TR key={p.id}>
              <TD>
                <Link href={`/dashboard/watchlist/${encodeURIComponent(p.id)}`} className="font-medium hover:underline">
                  {p.name}
                </Link>
                <div className="text-xs text-slate-500">{p.id}</div>
              </TD>
              <TD>{p.alias ?? '-'}</TD>
              <TD>{p.reason ?? '-'}</TD>
              <TD>
                <Badge variant={p.status === 'ACTIVE' ? 'default' : 'outline'}>{p.status}</Badge>
              </TD>
              <TD>{p.images?.length ?? 0}</TD>
              <TD>{p.updated_at ?? '-'}</TD>
            </TR>
          ))}
        </TBody>
      </Table>
    </div>
  );
}
