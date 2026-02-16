import * as React from 'react';

export const Textarea = React.forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(
  ({ className = '', ...props }, ref) => {
    return (
      <textarea
        ref={ref}
        className={`min-h-[96px] w-full rounded-xl px-3 py-2 text-sm shadow-sm outline-none input-field ${className}`}
        {...props}
      />
    );
  }
);
Textarea.displayName = 'Textarea';
