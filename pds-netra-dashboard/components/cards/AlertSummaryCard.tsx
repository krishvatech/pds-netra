import Link from 'next/link';
import { Card, CardContent, CardHeader } from '../ui/card';
import { Badge } from '../ui/badge';
import type { AlertItem } from '@/lib/types';
import { formatUtc, humanAlertType, severityBadgeClass } from '@/lib/formatters';

export function AlertSummaryCard({ alert }: { alert: AlertItem }) {
  return (
    <Card className="hover:shadow-lg transition animate-fade-up">
      <CardHeader className="flex items-start justify-between">
        <div>
          <div className="text-sm font-semibold font-display">{humanAlertType(alert.alert_type)}</div>
          <div className="text-xs text-slate-500">{alert.godown_name ?? alert.godown_id}</div>
        </div>
        <Badge className={severityBadgeClass(alert.severity_final)}>{alert.severity_final.toUpperCase()}</Badge>
      </CardHeader>
      <CardContent>
        <div className="text-xs text-slate-600">Started: {formatUtc(alert.start_time)}</div>
        <div className="text-xs text-slate-600">Status: {alert.status}</div>
        <div className="mt-3">
          <Link href={`/dashboard/alerts/${alert.id}`} className="text-sm underline">
            View details
          </Link>
        </div>
      </CardContent>
    </Card>
  );
}
