import * as React from 'react';

type Variant = 'default' | 'outline' | 'ghost' | 'danger';

type Props = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
};

export function Button({ variant = 'default', className = '', ...props }: Props) {
  const base = 'inline-flex items-center justify-center rounded-xl px-4 py-2 text-sm font-medium transition-all disabled:opacity-50 disabled:pointer-events-none';
  const v =
    variant === 'outline'
      ? 'btn-outline'
      : variant === 'ghost'
        ? 'hover:bg-white/70'
        : variant === 'danger'
          ? 'btn-danger'
          : 'btn-primary';
  return <button className={`${base} ${v} ${className}`} {...props} />;
}
