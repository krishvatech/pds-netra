import * as React from 'react';

type Variant = 'default' | 'outline' | 'ghost' | 'danger';
type Size = 'default' | 'icon';

type Props = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  size?: Size;
};

export function Button({ variant = 'default', size = 'default', className = '', ...props }: Props) {
  const base = 'inline-flex items-center justify-center rounded-xl text-sm font-medium transition-all disabled:opacity-50 disabled:pointer-events-none';
  const sizing = size === 'icon' ? 'h-9 w-9 px-0' : 'px-4 py-2';
  const v =
    variant === 'outline'
      ? 'btn-outline'
      : variant === 'ghost'
        ? 'hover:bg-white/70'
        : variant === 'danger'
          ? 'btn-danger'
          : 'btn-primary';
  return <button className={`${base} ${sizing} ${v} ${className}`} {...props} />;
}
