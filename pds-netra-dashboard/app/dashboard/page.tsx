'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { getToken } from '@/lib/auth';

export default function DashboardIndex() {
  const router = useRouter();

  useEffect(() => {
    const token = getToken();
    router.replace(token ? '/dashboard/overview' : '/dashboard/login');
  }, [router]);

  return null;
}
