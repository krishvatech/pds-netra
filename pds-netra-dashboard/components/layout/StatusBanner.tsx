'use client';

import { useEffect, useState } from 'react';

export function StatusBanner() {
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    let timer: number | undefined;

    const check = async () => {
      try {
        const resp = await fetch('/api/v1/health/summary', { cache: 'no-store' });
        setOffline(!resp.ok);
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

  if (!offline) return null;

  return (
    <div className="w-full bg-rose-600 text-white text-xs uppercase tracking-[0.3em] px-4 py-2 text-center">
      Backend offline — live data is unavailable
    </div>
  );
}
