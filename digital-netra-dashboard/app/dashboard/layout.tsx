import type { ReactNode } from 'react';
import { Header } from '@/components/layout/Header';
import { Sidebar } from '@/components/layout/Sidebar';

export default function DashboardLayout({ children }: { children: ReactNode }) {
  return (
    <div className="app-shell relative h-[100dvh] overflow-hidden bg-[#0b1020]">
      <div className="pointer-events-none absolute inset-0" aria-hidden>
        <div className="app-bg" />
        <div className="app-grid" />
        <div className="app-scanlines" />
        <div className="pointer-events-none absolute -top-24 right-12 h-64 w-64 rounded-full bg-gradient-to-br from-amber-400/40 via-orange-400/30 to-transparent blur-3xl animate-float" />
        <div className="pointer-events-none absolute bottom-[-120px] left-[-80px] h-72 w-72 rounded-full bg-gradient-to-tr from-sky-400/40 via-blue-400/30 to-transparent blur-3xl animate-float" />
        <div className="radar-wrap">
          <div className="radar-sweep" />
          <div className="radar-ring" />
          <div className="radar-grid" />
        </div>
      </div>

      <div className="relative z-10 flex h-full flex-col">
        <Header />
        <div className="flex min-h-0 flex-1">
          <Sidebar />
          <main className="flex-1 overflow-y-auto px-6 py-6">{children}</main>
        </div>
      </div>
    </div>
  );
}
