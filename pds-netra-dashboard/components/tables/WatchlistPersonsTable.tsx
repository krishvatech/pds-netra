import Link from 'next/link';
import { Badge } from '../ui/badge';
import type { WatchlistPerson } from '@/lib/types';
import { formatUtc } from '@/lib/formatters';

type WatchlistPersonsTableProps = {
  persons: WatchlistPerson[];
  onEdit: (person: WatchlistPerson) => void;
  onDelete: (person: WatchlistPerson) => void;
};

export function WatchlistPersonsTable({ persons, onEdit, onDelete }: WatchlistPersonsTableProps) {
  return (
    <div className="max-h-[60vh] overflow-y-auto overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-700">
            <th className="text-left py-3 px-2 text-slate-400 font-medium">Name</th>
            <th className="text-left py-3 px-2 text-slate-400 font-medium">Alias</th>
            <th className="text-left py-3 px-2 text-slate-400 font-medium">Reason</th>
            <th className="text-left py-3 px-2 text-slate-400 font-medium">Status</th>
            <th className="text-left py-3 px-2 text-slate-400 font-medium">Images</th>
            <th className="text-left py-3 px-2 text-slate-400 font-medium">Updated</th>
            <th className="text-right py-3 px-2 text-slate-400 font-medium">Actions</th>
          </tr>
        </thead>
        <tbody>
          {persons.length === 0 ? (
            <tr>
              <td colSpan={7} className="text-center py-8 text-slate-500">
                No blacklisted persons found
              </td>
            </tr>
          ) : (
            persons.map((p) => (
              <tr key={p.id} className="border-b border-slate-800 hover:bg-slate-800/50">
                <td className="py-3 px-2">
                  <Link href={`/dashboard/watchlist/${encodeURIComponent(p.id)}`} className="font-medium text-slate-200 hover:underline">
                    {p.name}
                  </Link>
                  <div className="text-xs text-slate-500">{p.id}</div>
                </td>
                <td className="py-3 px-2 text-slate-300">{p.alias ?? '—'}</td>
                <td className="py-3 px-2 text-slate-300">{p.reason ?? '—'}</td>
                <td className="py-3 px-2">
                  <Badge variant={p.status === 'ACTIVE' ? 'default' : 'outline'}>{p.status}</Badge>
                </td>
                <td className="py-3 px-2 text-slate-300">{p.images?.length ?? 0}</td>
                <td className="py-3 px-2 text-slate-400 text-xs">{p.updated_at ? formatUtc(p.updated_at) : '—'}</td>
                <td className="py-3 px-2 text-right space-x-2">
                  <button onClick={() => onEdit(p)} className="text-blue-400 hover:text-blue-300 text-xs">
                    Edit
                  </button>
                  <button onClick={() => onDelete(p)} className="text-red-400 hover:text-red-300 text-xs">
                    Delete
                  </button>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
