'use client';

import { useEffect, useState } from 'react';
import { getEvents, getHealthSummary } from '@/lib/api';

export function StatusBanner() {
  const [offline, setOffline] = useState(false);
  const [mqttDown, setMqttDown] = useState(false);
  const [eventsStale, setEventsStale] = useState(false);

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

  if (!offline && !mqttDown && !eventsStale) return null;

  return (
    <div className={`w-full px-3 py-2 text-center text-[10px] uppercase leading-relaxed tracking-[0.2em] text-white sm:px-4 sm:text-xs sm:tracking-[0.3em] ${offline ? 'bg-rose-600' : 'bg-amber-500/90'}`}>
      {offline
        ? 'Backend offline — live data is unavailable'
        : mqttDown
          ? 'MQTT consumer disconnected — edge events not arriving'
          : 'No events in the last 10 minutes — check edge and broker'}
    </div>
  );
}
