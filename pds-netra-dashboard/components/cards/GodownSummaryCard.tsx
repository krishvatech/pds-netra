import Link from 'next/link';
import { Card, CardContent, CardHeader } from '../ui/card';
import { Badge } from '../ui/badge';
import type { GodownListItem } from '@/lib/types';

function statusBadge(status: GodownListItem['status']) {
  if (status === 'CRITICAL') return <Badge className="bg-red-100 text-red-800 border-red-200">Critical</Badge>;
  if (status === 'ISSUES') return <Badge className="bg-yellow-100 text-yellow-800 border-yellow-200">Issues</Badge>;
  return <Badge className="bg-green-100 text-green-800 border-green-200">OK</Badge>;
}

export function GodownSummaryCard({ godown }: { godown: GodownListItem }) {
  return (
    <Link href={`/dashboard/godowns/${godown.godown_id}`} className="block">
      <Card className="hover:shadow-lg transition-shadow animate-fade-up">
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <div className="font-semibold font-display">{godown.name ?? godown.godown_id}</div>
            <div className="text-xs text-slate-500">{godown.district ?? '-'}</div>
          </div>
          {statusBadge(godown.status)}
        </CardHeader>
        <CardContent className="grid grid-cols-2 gap-2">
          <div className="text-sm">
            <div className="text-slate-500 text-xs">Open alerts</div>
            <div className="font-medium">{(godown.open_alerts_critical ?? 0) + (godown.open_alerts_warning ?? 0)}</div>
          </div>
          <div className="text-sm">
            <div className="text-slate-500 text-xs">Cameras</div>
            <div className="font-medium">{godown.cameras_total ?? 0}</div>
          </div>
          <div className="text-sm">
            <div className="text-slate-500 text-xs">Critical</div>
            <div className="font-medium text-red-700">{godown.open_alerts_critical ?? 0}</div>
          </div>
          <div className="text-sm">
            <div className="text-slate-500 text-xs">Camera issues</div>
            <div className="font-medium">{godown.cameras_offline ?? 0}</div>
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}
