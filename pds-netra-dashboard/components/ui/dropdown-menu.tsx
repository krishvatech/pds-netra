'use client';

import * as React from 'react';

type DropdownContextValue = {
  open: boolean;
  setOpen: (next: boolean) => void;
};

const DropdownContext = React.createContext<DropdownContextValue | null>(null);

function useDropdownContext() {
  const ctx = React.useContext(DropdownContext);
  if (!ctx) throw new Error('DropdownMenu components must be used within DropdownMenu.');
  return ctx;
}

export function DropdownMenu({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = React.useState(false);
  return (
    <DropdownContext.Provider value={{ open, setOpen }}>
      <div className="relative inline-flex">{children}</div>
    </DropdownContext.Provider>
  );
}

type TriggerProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  asChild?: boolean;
  children: React.ReactElement;
};

export function DropdownMenuTrigger({ asChild = false, children, ...props }: TriggerProps) {
  const { open, setOpen } = useDropdownContext();
  const triggerProps = {
    ...props,
    onClick: (e: React.MouseEvent<HTMLButtonElement>) => {
      props.onClick?.(e);
      if (!e.defaultPrevented) setOpen(!open);
    }
  };

  if (asChild) {
    return React.cloneElement(children, triggerProps);
  }
  return React.createElement('button', triggerProps, children);
}

export function DropdownMenuContent({
  className = '',
  align = 'end',
  children
}: {
  className?: string;
  align?: 'start' | 'end';
  children: React.ReactNode;
}) {
  const { open, setOpen } = useDropdownContext();
  const ref = React.useRef<HTMLDivElement | null>(null);

  React.useEffect(() => {
    if (!open) return;
    const onDocClick = (e: MouseEvent) => {
      if (!ref.current) return;
      if (e.target instanceof Node && !ref.current.contains(e.target)) {
        setOpen(false);
      }
    };
    const onEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onDocClick);
    document.addEventListener('keydown', onEscape);
    return () => {
      document.removeEventListener('mousedown', onDocClick);
      document.removeEventListener('keydown', onEscape);
    };
  }, [open, setOpen]);

  if (!open) return null;

  return (
    <div
      ref={ref}
      className={`absolute z-40 mt-2 min-w-[170px] rounded-xl border border-white/15 bg-slate-950/90 p-1 shadow-xl backdrop-blur ${
        align === 'end' ? 'right-0' : 'left-0'
      } ${className}`}
      role="menu"
    >
      {children}
    </div>
  );
}

export function DropdownMenuLabel({ className = '', ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={`px-2 py-1.5 text-xs text-slate-400 ${className}`} {...props} />;
}

export function DropdownMenuSeparator({ className = '', ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={`my-1 h-px bg-white/10 ${className}`} {...props} />;
}

type ItemProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  destructive?: boolean;
};

export function DropdownMenuItem({ className = '', destructive = false, ...props }: ItemProps) {
  const { setOpen } = useDropdownContext();
  return (
    <button
      className={`flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left text-sm transition ${
        destructive ? 'text-rose-300 hover:bg-rose-500/15' : 'text-slate-200 hover:bg-white/10'
      } ${className}`}
      {...props}
      onClick={(e) => {
        props.onClick?.(e);
        if (!e.defaultPrevented) setOpen(false);
      }}
    />
  );
}
