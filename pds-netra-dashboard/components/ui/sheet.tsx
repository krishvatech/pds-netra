'use client';

import * as React from 'react';

type SheetContextValue = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

const SheetContext = React.createContext<SheetContextValue | null>(null);

function useSheetContext() {
  const ctx = React.useContext(SheetContext);
  if (!ctx) throw new Error('Sheet components must be used within Sheet.');
  return ctx;
}

type SheetProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  children: React.ReactNode;
};

export function Sheet({ open, onOpenChange, children }: SheetProps) {
  React.useEffect(() => {
    if (!open) return;
    const onEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onOpenChange(false);
    };
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    document.addEventListener('keydown', onEscape);
    return () => {
      document.body.style.overflow = prev;
      document.removeEventListener('keydown', onEscape);
    };
  }, [open, onOpenChange]);

  return <SheetContext.Provider value={{ open, onOpenChange }}>{children}</SheetContext.Provider>;
}

export function SheetContent({
  side = 'right',
  className = '',
  children
}: {
  side?: 'right' | 'left';
  className?: string;
  children: React.ReactNode;
}) {
  const { open, onOpenChange } = useSheetContext();
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50">
      <button
        className="absolute inset-0 bg-slate-950/70 backdrop-blur-[1px]"
        onClick={() => onOpenChange(false)}
        aria-label="Close"
      />
      <div
        className={`absolute bottom-0 top-0 w-full max-w-xl border-l border-white/10 bg-slate-950/95 shadow-2xl ${
          side === 'right' ? 'right-0' : 'left-0 border-l-0 border-r'
        } ${className}`}
      >
        {children}
      </div>
    </div>
  );
}

export function SheetHeader({ className = '', ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={`space-y-1 border-b border-white/10 p-4 ${className}`} {...props} />;
}

export function SheetTitle({ className = '', ...props }: React.HTMLAttributes<HTMLHeadingElement>) {
  return <h3 className={`text-lg font-semibold text-slate-100 ${className}`} {...props} />;
}

export function SheetDescription({ className = '', ...props }: React.HTMLAttributes<HTMLParagraphElement>) {
  return <p className={`text-sm text-slate-300 ${className}`} {...props} />;
}
