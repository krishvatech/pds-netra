'use client';

import { useEffect, useMemo, useState } from 'react';
import { getGodownDetail, getGodowns } from '@/lib/api';
import type { GodownDetail, GodownListItem } from '@/lib/types';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { ErrorBanner } from '@/components/ui/error-banner';

export default function LiveCamerasPage() {
  const [godowns, setGodowns] = useState<GodownListItem[]>([]);
  const [selectedGodown, setSelectedGodown] = useState<string>('');
  const [godownDetail, setGodownDetail] = useState<GodownDetail | null>(null);
  const [selectedCamera, setSelectedCamera] = useState<string>('');
  const [error, setError] = useState<string | null>(null);
  const [streamNonce, setStreamNonce] = useState(0);

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const resp = await getGodowns({ page: 1, page_size: 200 });
        const items = Array.isArray(resp) ? resp : resp.items;
        if (!mounted) return;
        setGodowns(items);
        if (items.length > 0 && !selectedGodown) {
          setSelectedGodown(items[0].godown_id);
        }
      } catch (e) {
        if (mounted) setError(e instanceof Error ? e.message : 'Failed to load godowns');
      }
    })();
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    let mounted = true;
    if (!selectedGodown) return;
    (async () => {
      try {
        const detail = await getGodownDetail(selectedGodown);
        if (!mounted) return;
        setGodownDetail(detail);
        if (detail.cameras.length > 0) {
          setSelectedCamera((prev) => prev || detail.cameras[0].camera_id);
        }
      } catch (e) {
        if (mounted) setError(e instanceof Error ? e.message : 'Failed to load cameras');
      }
    })();
    return () => {
      mounted = false;
    };
  }, [selectedGodown]);

  const cameras = godownDetail?.cameras ?? [];
  const streamUrl = useMemo(() => {
    if (!selectedGodown || !selectedCamera) return '';
    return `/api/v1/live/${encodeURIComponent(selectedGodown)}/${encodeURIComponent(selectedCamera)}?v=${streamNonce}`;
  }, [selectedGodown, selectedCamera, streamNonce]);

  return (
    <div className="space-y-5">
      <Card className="animate-fade-up">
        <CardHeader>
          <div className="text-xl font-semibold font-display">Live Cameras</div>
          <div className="text-sm text-slate-600">Annotated live frames from edge.</div>
        </CardHeader>
        <CardContent className="space-y-4">
          {error && <ErrorBanner message={error} onRetry={() => window.location.reload()} />}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <label className="text-sm text-slate-600">
              Godown
              <select
                className="mt-2 w-full rounded-xl border border-white/40 bg-white/80 px-3 py-2 text-sm text-slate-800"
                value={selectedGodown}
                onChange={(e) => setSelectedGodown(e.target.value)}
              >
                {godowns.map((g, idx) => (
                  <option key={`${g.godown_id}-${idx}`} value={g.godown_id}>
                    {g.name ?? g.godown_id ?? `Godown ${idx + 1}`}
                  </option>
                ))}
              </select>
            </label>
            <div className="flex items-end">
              <Button variant="outline" onClick={() => setStreamNonce((n) => n + 1)}>
                Refresh stream
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="text-lg font-semibold font-display">Live annotated feeds</div>
          <div className="text-sm text-slate-600">
            Live view for {selectedGodown || 'selected godown'} cameras.
          </div>
        </CardHeader>
        <CardContent>
          {cameras.length > 0 ? (
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
              {cameras.map((camera) => {
                const camUrl = `/api/v1/live/${encodeURIComponent(selectedGodown)}/${encodeURIComponent(
                  camera.camera_id
                )}?v=${streamNonce}`;
                return (
                  <div key={camera.camera_id} className="space-y-3">
                    <div className="text-base font-semibold text-slate-800">
                      {camera.label ?? camera.camera_id}
                    </div>
                    <div className="aspect-video w-full overflow-hidden rounded-2xl border border-white/40 bg-black/80 shadow-inner">
                      <img
                        src={camUrl}
                        alt={`Live ${camera.camera_id}`}
                        className="h-full w-full object-cover"
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="text-sm text-slate-600">No cameras available for this godown.</div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
