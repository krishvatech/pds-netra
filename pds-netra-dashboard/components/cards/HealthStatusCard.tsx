import { Badge } from '../ui/badge';
import { Card, CardContent, CardHeader } from '../ui/card';

export function HealthStatusCard({
  title,
  value,
  variant = 'outline',
  tone = 'default'
}: {
  title: string;
  value: string | number;
  variant?: 'default' | 'outline';
  tone?: 'default' | 'warning';
}) {
  return (
    <Card
      className={`animate-fade-up shadow-sm ${tone === 'warning' ? 'border-amber-400/30 bg-amber-500/5' : ''}`}
    >
      <CardHeader className="border-b-0 pb-1">
        <div className="text-xs uppercase tracking-widest text-slate-400">{title}</div>
      </CardHeader>
      <CardContent className="flex items-center justify-between pt-0">
        <div className="text-3xl font-semibold">{value}</div>
        <Badge variant={variant} className="text-[11px] uppercase tracking-widest opacity-80">
          Live
        </Badge>
      </CardContent>
    </Card>
  );
}
