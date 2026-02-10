'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { getSessionUser } from '@/lib/auth';

export default function DashboardIndex() {
  const router = useRouter();

  useEffect(() => {
    let active = true;
    (async () => {
      const user = await getSessionUser();
      if (!active) return;
      if (!user) {
        router.replace('/dashboard/login');
        return;
      }
      if (user.role === 'STATE_ADMIN') {
        router.replace('/dashboard/command-center');
        return;
      }
      if (user.role === 'DISTRICT_OFFICER') {
        router.replace('/dashboard/district');
        return;
      }
      if (user.role === 'GODOWN_MANAGER' && user.godown_id) {
        router.replace(`/dashboard/godowns/${encodeURIComponent(user.godown_id)}`);
        return;
      }
      router.replace('/dashboard/overview');
    })();
    return () => {
      active = false;
    };
  }, [router]);

  return null;
}
