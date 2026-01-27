'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { getToken, getUser } from '@/lib/auth';

export default function DashboardIndex() {
  const router = useRouter();

  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.replace('/dashboard/login');
      return;
    }
    const user = getUser();
    if (user?.role === 'STATE_ADMIN') {
      router.replace('/dashboard/command-center');
      return;
    }
    if (user?.role === 'DISTRICT_OFFICER') {
      router.replace('/dashboard/district');
      return;
    }
    if (user?.role === 'GODOWN_MANAGER' && user.godown_id) {
      router.replace(`/dashboard/godowns/${encodeURIComponent(user.godown_id)}`);
      return;
    }
    router.replace('/dashboard/overview');
  }, [router]);

  return null;
}
