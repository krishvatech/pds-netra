'use client';

import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip } from 'recharts';
import { Card, CardContent, CardHeader } from '../ui/card';

export type AlertsByTypePoint = { name: string; count: number };

export function AlertsByTypeChart({ data }: { data: AlertsByTypePoint[] }) {
  return (
    <Card className="animate-fade-up">
      <CardHeader>
        <div className="text-sm text-slate-600">Alerts by type</div>
      </CardHeader>
      <CardContent>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data}>
              <XAxis dataKey="name" tick={{ fontSize: 12 }} interval={0} angle={-20} height={60} />
              <YAxis allowDecimals={false} />
              <Tooltip />
              <Bar dataKey="count" fill="#f59e0b" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}
