'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { AlertBox } from '@/components/ui/alert-box';
import { getSessionUser, getToken } from '@/lib/auth';
import type { Camera } from '@/lib/types';
import { getLiveCameras } from '@/lib/api';

type LiveFrameState = {
  url: string | null;
  ageSeconds: number | null;
  stale: boolean;
  error: string | null;
  loading: boolean;
};

function AuthedLiveImage({ cameraId }: { cameraId: string }) {
  const token = getToken();
  const [state, setState] = useState<LiveFrameState>({
    url: null,
    ageSeconds: null,
    stale: false,
    error: null,
    loading: true
  });
  const controllerRef = useRef<AbortController | null>(null);
  const timerRef = useRef<number | null>(null);
  const urlRef = useRef<string | null>(null);

  useEffect(() => {
    let mounted = true;

    async function fetchFrame() {
      if (!mounted) return;

      controllerRef.current?.abort();
      const controller = new AbortController();
      controllerRef.current = controller;

      setState((prev) => ({ ...prev, loading: prev.url === null }));

      try {
        const headers = new Headers();
        if (token) headers.set('Authorization', `Bearer ${token}`);
        const resp = await fetch(`/api/v1/live/frame/${cameraId}`, {
          headers,
          credentials: 'include',
          cache: 'no-store',
          signal: controller.signal
        });

        if (!mounted) return;

        if (resp.status === 404) {
          setState({ url: null, ageSeconds: null, stale: true, error: null, loading: false });
        } else if (!resp.ok) {
          setState((prev) => ({ ...prev, error: 'Unable to load frame.', loading: false }));
        } else {
          const blob = await resp.blob();
          const nextUrl = URL.createObjectURL(blob);
          if (urlRef.current) URL.revokeObjectURL(urlRef.current);
          urlRef.current = nextUrl;
          const ageHeader = resp.headers.get('x-frame-age-seconds');
          const staleHeader = resp.headers.get('x-frame-stale');
          const ageSeconds = ageHeader ? Number.parseFloat(ageHeader) : null;
          const stale = staleHeader === 'true' || (ageSeconds !== null ? ageSeconds > 30 : false);
          setState({ url: nextUrl, ageSeconds, stale, error: null, loading: false });
        }
      } catch (err) {
        if (!mounted) return;
        setState((prev) => ({ ...prev, error: 'Feed unavailable.', loading: false }));
      } finally {
        scheduleNext();
      }
    }

    function scheduleNext() {
      if (!mounted) return;
      if (timerRef.current) window.clearTimeout(timerRef.current);
      const delay = document.hidden ? 5000 : 1000;
      timerRef.current = window.setTimeout(fetchFrame, delay);
    }

    function handleVisibilityChange() {
      scheduleNext();
    }

    fetchFrame();
    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      mounted = false;
      controllerRef.current?.abort();
      if (timerRef.current) window.clearTimeout(timerRef.current);
      if (urlRef.current) URL.revokeObjectURL(urlRef.current);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [cameraId, token]);

  const ageLabel = state.ageSeconds !== null ? `${state.ageSeconds.toFixed(1)}s` : '—';
  const ageClass =
    state.ageSeconds === null
      ? 'sev-warning'
      : state.ageSeconds <= 5
        ? 'sev-info'
        : state.ageSeconds <= 20
          ? 'sev-warning'
          : 'sev-critical';

  return (
    <div className="relative overflow-hidden rounded-xl border border-white/10 bg-slate-950/40">
      <div className="aspect-video w-full">
        {state.url ? (
          <img src={state.url} alt="Live frame" className="h-full w-full object-cover" />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-xs uppercase tracking-[0.3em] text-slate-400">
            {state.loading ? 'Loading…' : 'No Feed'}
          </div>
        )}
      </div>

      <div className="absolute left-3 top-3 flex items-center gap-2">
        <span className={['hud-pill', ageClass].join(' ')}>Age {ageLabel}</span>
        {state.stale && <span className="hud-pill sev-warning">Stale</span>}
      </div>

      {state.error && (
        <div className="absolute bottom-3 left-3 rounded-full border border-white/15 bg-white/10 px-3 py-1 text-xs text-slate-200">
          {state.error}
        </div>
      )}
    </div>
  );
}

export default function LiveFeedPage() {
  const router = useRouter();
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let intervalId: number | null = null;

    async function guard() {
      const user = await getSessionUser();
      if (!user) {
        router.replace('/auth/login');
        return;
      }
      await loadCameras();
      intervalId = window.setInterval(loadCameras, 10000);
    }

    guard();
    return () => {
      if (intervalId) window.clearInterval(intervalId);
    };
  }, [router]);

  async function loadCameras() {
    setError(null);
    setLoading(true);
    try {
      const data = await getLiveCameras();
      setCameras(data);
    } catch (err) {
      setError('Unable to load live cameras.');
    } finally {
      setLoading(false);
    }
  }

  const activeCount = useMemo(() => cameras.length, [cameras]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="space-y-2">
          <div className="hud-pill">
            <span className="pulse-dot pulse-info" />
            Live
          </div>
          <div className="text-4xl font-semibold font-display tracking-tight text-slate-100 drop-shadow">
            Live Feed
          </div>
          <div className="text-sm text-slate-300">
            Monitor active cameras in near real-time.
          </div>
        </div>
        <div className="hud-card px-4 py-2 text-xs text-slate-300">Active {activeCount}</div>
      </div>

      {error && <AlertBox variant="error">{error}</AlertBox>}

      {loading ? (
        <div className="hud-card p-6 text-sm text-slate-300">Loading live feeds…</div>
      ) : cameras.length === 0 ? (
        <div className="hud-card p-6">
          <div className="text-lg font-semibold font-display">No active cameras</div>
          <div className="text-sm text-slate-400 mt-2">Activate a camera to view live feeds.</div>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 xl:grid-cols-3">
          {cameras.map((camera) => (
            <div key={camera.id} className="hud-card p-4 space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-base font-semibold text-slate-100">{camera.camera_name}</div>
                  <div className="text-xs uppercase tracking-[0.25em] text-slate-400">{camera.role}</div>
                </div>
                <span className="hud-pill sev-info">Active</span>
              </div>
              <AuthedLiveImage cameraId={camera.id} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
