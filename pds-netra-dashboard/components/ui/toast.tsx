'use client';

import { useEffect } from 'react';

export type ToastItem = {
  id: string;
  title: string;
  message?: string;
  type?: 'success' | 'error' | 'info';
  durationMs?: number;
};

type ToastStackProps = {
  items: ToastItem[];
  onDismiss: (id: string) => void;
};

export function ToastStack({ items, onDismiss }: ToastStackProps) {
  useEffect(() => {
    if (items.length === 0) return;
    const timers = items.map((item) => {
      const duration = item.durationMs ?? 3200;
      return window.setTimeout(() => onDismiss(item.id), duration);
    });
    return () => {
      timers.forEach((t) => window.clearTimeout(t));
    };
  }, [items, onDismiss]);

  if (items.length === 0) return null;

  return (
    <div className="fixed right-5 top-5 z-50 flex w-[320px] max-w-[90vw] flex-col gap-3">
      {items.map((toast) => {
        const tone =
          toast.type === 'success'
            ? 'border-emerald-400/60'
            : toast.type === 'error'
              ? 'border-rose-400/60'
              : 'border-amber-300/60';
        return (
          <div key={toast.id} className={`alert-toast border-l-4 ${tone} px-4 py-3`}>
            <div className="text-sm font-semibold text-slate-100">{toast.title}</div>
            {toast.message && <div className="mt-1 text-xs text-slate-300">{toast.message}</div>}
          </div>
        );
      })}
    </div>
  );
}

