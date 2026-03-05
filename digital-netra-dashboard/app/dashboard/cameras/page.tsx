'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { getSessionUser } from '@/lib/auth';

export default function CamerasPage() {
  const router = useRouter();

  useEffect(() => {
    async function guard() {
      const user = await getSessionUser();
      if (!user) router.replace('/auth/login');
    }
    guard();
  }, [router]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="space-y-2">
          <div className="hud-pill">
            <span className="pulse-dot pulse-info" />
            Live
          </div>
          <div className="text-4xl font-semibold font-display tracking-tight text-slate-100 drop-shadow">
            Cameras
          </div>
          <div className="text-sm text-slate-300">Camera fleet overview will appear here.</div>
        </div>
      </div>

      <div className="hud-card p-6">
        <div className="text-lg font-semibold font-display">Coming soon</div>
        <div className="text-sm text-slate-400 mt-2">We are preparing the camera monitoring experience.</div>
      </div>
    </div>
  );
}
