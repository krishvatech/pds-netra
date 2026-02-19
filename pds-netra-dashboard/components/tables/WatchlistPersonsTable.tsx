import Link from 'next/link';
import { Badge } from '../ui/badge';
import { ConfirmDeletePopover } from '../ui/dialog';
import { EmptyState } from '../ui/empty-state';
import { Skeleton } from '../ui/skeleton';
import type { WatchlistPerson } from '@/lib/types';
import { formatUtc } from '@/lib/formatters';
import { UserX } from 'lucide-react';

type WatchlistPersonsTableProps = {
  persons: WatchlistPerson[];
  onEdit: (person: WatchlistPerson) => void;
  onDelete: (person: WatchlistPerson) => void;
  deleteBusyId?: string | null;
  isLoading?: boolean;
  onEmptyAction?: () => void;
};

export function WatchlistPersonsTable({
  persons,
  onEdit,
  onDelete,
  deleteBusyId,
  isLoading = false,
  onEmptyAction
}: WatchlistPersonsTableProps) {
  return (
    <div className="min-h-[260px] overflow-x-auto rounded-xl border border-white/10 bg-slate-950/40">
      <table className="min-w-[720px] w-full text-sm">
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
          {isLoading
            ? Array.from({ length: 6 }).map((_, idx) => (
                <tr key={`skeleton-${idx}`} className="border-b border-slate-800">
                  <td className="py-3 px-2">
                    <Skeleton className="h-4 w-40" />
                    <Skeleton className="mt-2 h-3 w-24" />
                  </td>
                  <td className="py-3 px-2">
                    <Skeleton className="h-4 w-20" />
                  </td>
                  <td className="py-3 px-2">
                    <Skeleton className="h-4 w-24" />
                  </td>
                  <td className="py-3 px-2">
                    <Skeleton className="h-5 w-16 rounded-full" />
                  </td>
                  <td className="py-3 px-2">
                    <Skeleton className="h-4 w-10" />
                  </td>
                  <td className="py-3 px-2">
                    <Skeleton className="h-3 w-24" />
                  </td>
                  <td className="py-3 px-2 text-right">
                    <Skeleton className="ml-auto h-4 w-16" />
                  </td>
                </tr>
              ))
            : persons.map((p) => (
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
                    <ConfirmDeletePopover
                      title="Delete blacklisted person?"
                      description={`This will remove ${p.name} from active watchlist operations. This action cannot be undone.`}
                      confirmText="Delete"
                      onConfirm={() => onDelete(p)}
                      isBusy={deleteBusyId === p.id}
                    >
                      <button className="text-red-400 hover:text-red-300 text-xs">
                        Delete
                      </button>
                    </ConfirmDeletePopover>
                  </td>
                </tr>
              ))}
        </tbody>
      </table>
      {!isLoading && persons.length === 0 ? (
        <div className="px-4 pb-6">
          <EmptyState
            icon={<UserX className="h-5 w-5" />}
            title="No blacklisted persons yet"
            message="Create the first watchlist profile to start tracking high-risk identities."
            actionLabel={onEmptyAction ? 'Add person' : undefined}
            onAction={onEmptyAction}
          />
        </div>
      ) : null}
    </div>
  );
}
