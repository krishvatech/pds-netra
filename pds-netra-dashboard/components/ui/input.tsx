import * as React from 'react';

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className = '', ...props }, ref) => {
    return (
      <input
        ref={ref}
        className={`h-11 w-full rounded-xl border border-white/60 bg-white/80 px-3 py-2 text-sm text-slate-900 shadow-sm outline-none transition focus:border-amber-400 focus:ring-2 focus:ring-amber-200 ${className}`}
        {...props}
      />
    );
  }
);
Input.displayName = 'Input';
