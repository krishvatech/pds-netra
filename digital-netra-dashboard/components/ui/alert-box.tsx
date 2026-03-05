import type { ReactNode } from 'react';

type AlertVariant = 'success' | 'error' | 'warning';

type AlertBoxProps = {
  variant: AlertVariant;
  children: ReactNode;
  className?: string;
};

const VARIANT_CLASSES: Record<AlertVariant, string> = {
  success: 'bg-emerald-500/15 border-emerald-500/40 text-emerald-300',
  error: 'bg-red-500/15 border-red-500/40 text-red-300',
  warning: 'bg-amber-500/15 border-amber-500/40 text-amber-300'
};

export function AlertBox({ variant, children, className }: AlertBoxProps) {
  const classes = ['rounded-xl border px-4 py-3 text-sm', VARIANT_CLASSES[variant], className]
    .filter(Boolean)
    .join(' ');
  return <div className={classes}>{children}</div>;
}
