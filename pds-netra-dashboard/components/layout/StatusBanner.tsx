'use client';

import { useEffect, useState } from 'react';

export function StatusBanner() {
  const [offline, setOffline] = useState(false);
  const [mqttDown, setMqttDown] = useState(false);
  const [eventsStale, setEventsStale] = useState(false);

  useEffect(() => {
    let timer: number | undefined;

    const check = async () => {
      try {
        const resp = await fetch('/api/v1/health/summary', { cache: 'no-store' });
        if (!resp.ok) {
          setOffline(true);
          return;
        }
        const data = await resp.json();
        setOffline(false);
        if (data?.mqtt_consumer?.enabled) {
          setMqttDown(!data.mqtt_consumer.connected);
        } else {
          setMqttDown(false);
        }
        const eventsResp = await fetch('/api/v1/events?page=1&page_size=1', { cache: 'no-store' });
        if (eventsResp.ok) {
          const eventsData = await eventsResp.json();
          const first = eventsData?.items?.[0];
          if (first?.timestamp_utc) {
            const lastTs = new Date(first.timestamp_utc).getTime();
            const now = Date.now();
            setEventsStale(now - lastTs > 10 * 60 * 1000);
          } else {
            setEventsStale(true);
          }
        } else {
          setEventsStale(false);
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

  if (!offline && !mqttDown && !eventsStale) return null;

  return (
    <div className={`w-full text-white text-xs uppercase tracking-[0.3em] px-4 py-2 text-center ${offline ? 'bg-rose-600' : 'bg-amber-500/90'}`}>
      {offline
        ? 'Backend offline — live data is unavailable'
        : mqttDown
          ? 'MQTT consumer disconnected — edge events not arriving'
          : 'No events in the last 10 minutes — check edge and broker'}
    </div>
  );
}
