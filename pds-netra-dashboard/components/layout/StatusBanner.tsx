'use client';

import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { getEvents, getHealthSummary } from '@/lib/api';

export function StatusBanner({ onHeightChange }: { onHeightChange?: (height: number) => void }) {
  const [offline, setOffline] = useState(false);
  const [mqttDown, setMqttDown] = useState(false);
  const [eventsStale, setEventsStale] = useState(false);
  const [dismissed, setDismissed] = useState(false);
  const bannerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    let timer: number | undefined;

    const check = async () => {
      try {
        const data = await getHealthSummary();
        setOffline(false);
        if (data?.mqtt_consumer?.enabled) {
          setMqttDown(!data.mqtt_consumer.connected);
        } else {
          setMqttDown(false);
        }
        const eventsData = await getEvents({ page: 1, page_size: 1 });
        const first = Array.isArray(eventsData) ? eventsData[0] : eventsData?.items?.[0];
        if (first?.timestamp_utc) {
          const lastTs = new Date(first.timestamp_utc).getTime();
          const now = Date.now();
          setEventsStale(now - lastTs > 10 * 60 * 1000);
        } else {
          setEventsStale(true);
        }
      } catch {
        setOffline(true);
      }
    };

    check();
    timer = window.setInterval(check, 30000);

    return () => {
      if (timer) window.clearInterval(timer);
    };
  }, []);

  const shouldShow = (offline || mqttDown || eventsStale) && !dismissed;

  useLayoutEffect(() => {
    if (!onHeightChange) return;
    if (!shouldShow) {
      onHeightChange(0);
      return;
    }
    const measure = () => {
      const height = bannerRef.current ? Math.round(bannerRef.current.getBoundingClientRect().height) : 0;
      onHeightChange(height);
    };
    measure();
    const raf = requestAnimationFrame(measure);
    return () => cancelAnimationFrame(raf);
  }, [onHeightChange, shouldShow]);

  if (!shouldShow) return null;

  return (
    <div
      ref={bannerRef}
      className={`w-full ${offline ? 'bg-rose-600' : 'bg-amber-500/90'}`}
      role="status"
      aria-live="polite"
    >
      <div className="mx-auto flex w-full max-w-[1200px] min-w-0 items-center justify-between gap-3 px-4 py-2 text-xs uppercase tracking-[0.2em] text-white/90 md:px-6 lg:px-8">
        <span className="min-w-0 flex-1 truncate text-[11px] leading-relaxed md:text-xs">
          {offline
            ? 'Backend offline — live data is unavailable'
            : mqttDown
              ? 'MQTT consumer disconnected — edge events not arriving'
              : 'No events in the last 10 minutes — check edge and broker'}
        </span>
        <button
          type="button"
          className="shrink-0 rounded-full border border-white/30 px-2 py-1 text-[10px] uppercase tracking-[0.2em] text-white/80 hover:text-white"
          onClick={() => setDismissed(true)}
        >
          Dismiss
        </button>
      </div>
    </div>
  );
}
