import { Card, CardContent, CardHeader } from '../ui/card';
import { Badge } from '../ui/badge';

export function HealthStatusCard({
  title,
  value,
  variant = 'outline'
}: {
  title: string;
  value: string | number;
  variant?: 'default' | 'outline';
}) {
  return (
    <Card className="animate-fade-up">
      <CardHeader>
        <div className="text-xs uppercase tracking-[0.3em] text-slate-500">{title}</div>
      </CardHeader>
      <CardContent className="flex items-center justify-between">
        <div className="text-3xl font-semibold font-display">{value}</div>
        <Badge variant={variant} className="text-[11px] uppercase tracking-widest">
          Live
        </Badge>
      </CardContent>
    </Card>
  );
}
