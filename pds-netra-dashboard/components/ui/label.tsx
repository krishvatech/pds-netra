import * as React from 'react';

export function Label({ className = '', ...props }: React.LabelHTMLAttributes<HTMLLabelElement>) {
  return <label className={`text-[11px] uppercase tracking-[0.2em] text-slate-600 ${className}`} {...props} />;
}
