import * as React from 'react';

type Props = React.HTMLAttributes<HTMLSpanElement> & {
  variant?: 'default' | 'outline';
};

export function Badge({ variant = 'default', className = '', ...props }: Props) {
  const base = 'inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium badge-soft';
  const v = variant === 'outline' ? 'bg-transparent text-slate-700' : 'bg-white/70 text-slate-800';
  return <span className={`${base} ${v} ${className}`} {...props} />;
}
