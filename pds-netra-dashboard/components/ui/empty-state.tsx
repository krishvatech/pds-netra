import type { ReactNode } from 'react';
import { Button } from '@/components/ui/button';

type EmptyStateProps = {
  icon?: ReactNode;
  title: string;
  message: string;
  actionLabel?: string;
  onAction?: () => void;
  className?: string;
};

export function EmptyState({ icon, title, message, actionLabel, onAction, className = '' }: EmptyStateProps) {
  return (
    <div
      className={`flex flex-col items-center justify-center gap-3 rounded-2xl border border-white/10 bg-white/5 px-4 py-8 text-center ${className}`}
    >
      {icon ? (
        <span className="inline-flex h-12 w-12 items-center justify-center rounded-full border border-white/10 bg-white/5 text-slate-300">
          {icon}
        </span>
      ) : null}
      <div className="text-lg font-semibold text-slate-100">{title}</div>
      <p className="max-w-[420px] text-sm text-slate-400">{message}</p>
      {actionLabel && onAction ? (
        <Button variant="outline" onClick={onAction} className="mt-1">
          {actionLabel}
        </Button>
      ) : null}
    </div>
  );
}
