'use client';

import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip } from 'recharts';
import { Card, CardContent, CardHeader } from '../ui/card';

export type AlertsOverTimePoint = { t: string; count: number };

export function AlertsOverTimeChart({ data }: { data: AlertsOverTimePoint[] }) {
  return (
    <Card className="animate-fade-up">
      <CardHeader>
        <div className="text-sm text-slate-600">Alerts over time</div>
      </CardHeader>
      <CardContent>
        <div className="h-64 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
              <XAxis dataKey="t" tick={{ fontSize: 12 }} />
              <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
              <Tooltip />
              <Line type="monotone" dataKey="count" stroke="#0ea5e9" strokeWidth={2.5} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}
