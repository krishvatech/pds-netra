import * as React from 'react';

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className = '', ...props }, ref) => {
    return (
      <input
        ref={ref}
        className={`h-11 w-full rounded-xl px-3 py-2 text-sm shadow-sm outline-none input-field ${className}`}
        {...props}
      />
    );
  }
);
Input.displayName = 'Input';
