'use client';

import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip } from 'recharts';
import { Card, CardContent, CardHeader } from '../ui/card';

const COLORS = ['#38bdf8', '#f59e0b', '#22c55e', '#f43f5e', '#0ea5e9', '#14b8a6'];

type SeriesPoint = { t: string; [key: string]: string | number };

export function MovementTimelineChart({
  data,
  series
}: {
  data: SeriesPoint[];
  series: string[];
}) {
  return (
    <Card className="animate-fade-up hud-card">
      <CardHeader>
        <div className="text-sm text-slate-300">Movement activity timeline</div>
      </CardHeader>
      <CardContent>
        <div className="flex flex-wrap gap-2 text-xs text-slate-300 mb-3">
          {series.map((name, idx) => (
            <span key={name} className="inline-flex items-center gap-2">
              <span className="h-2 w-2 rounded-full" style={{ background: COLORS[idx % COLORS.length] }} />
              {name.replaceAll('_', ' ')}
            </span>
          ))}
        </div>
        <div className="h-64 w-full">
          {data.length === 0 ? (
            <div className="text-sm text-slate-400">No movement events for this range.</div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                <XAxis dataKey="t" tick={{ fontSize: 12, fill: '#cbd5f5' }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 12, fill: '#cbd5f5' }} />
                <Tooltip />
                {series.map((key, idx) => (
                  <Area
                    key={key}
                    type="monotone"
                    dataKey={key}
                    stackId="1"
                    stroke={COLORS[idx % COLORS.length]}
                    fill={COLORS[idx % COLORS.length]}
                    fillOpacity={0.3}
                  />
                ))}
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
