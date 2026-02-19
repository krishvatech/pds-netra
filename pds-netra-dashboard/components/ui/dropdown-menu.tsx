'use client';

import * as React from 'react';
import { createPortal } from 'react-dom';
import { usePathname } from 'next/navigation';

type DropdownContextValue = {
  open: boolean;
  setOpen: (next: boolean) => void;
  triggerRef: React.RefObject<HTMLElement>;
};

const DropdownContext = React.createContext<DropdownContextValue | null>(null);

function useDropdownContext() {
  const ctx = React.useContext(DropdownContext);
  if (!ctx) throw new Error('DropdownMenu components must be used within DropdownMenu.');
  return ctx;
}

function assignRef<T>(ref: React.Ref<T> | undefined, value: T | null) {
  if (!ref) return;
  if (typeof ref === 'function') {
    ref(value);
  } else {
    (ref as React.MutableRefObject<T | null>).current = value;
  }
}

export function DropdownMenu({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = React.useState(false);
  const triggerRef = React.useRef<HTMLElement>(null);
  return (
    <DropdownContext.Provider value={{ open, setOpen, triggerRef }}>
      {children}
    </DropdownContext.Provider>
  );
}

type TriggerProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  asChild?: boolean;
  children: React.ReactElement;
};

export function DropdownMenuTrigger({ asChild = false, children, ...props }: TriggerProps) {
  const { open, setOpen, triggerRef } = useDropdownContext();
  const childOnClick = (children as React.ReactElement).props?.onClick as
    | ((event: React.MouseEvent<HTMLButtonElement>) => void)
    | undefined;
  const triggerProps = {
    ...props,
    onClick: (e: React.MouseEvent<HTMLButtonElement>) => {
      childOnClick?.(e);
      props.onClick?.(e);
      if (!e.defaultPrevented) setOpen(!open);
    }
  };

  if (asChild) {
    const child = React.Children.only(children);
    return React.cloneElement(child, {
      ...triggerProps,
      ref: (node: HTMLElement | null) => {
        triggerRef.current = node ?? null;
        assignRef((child as any).ref, node);
      }
    });
  }

  return React.createElement('button', {
    ...triggerProps,
    ref: triggerRef
  }, children);
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
  const { open, setOpen, triggerRef } = useDropdownContext();
  const ref = React.useRef<HTMLDivElement | null>(null);
  const [mounted, setMounted] = React.useState(false);
  const [styles, setStyles] = React.useState<React.CSSProperties>({});
  const pathname = usePathname();

  React.useEffect(() => {
    setMounted(true);
  }, []);

  React.useEffect(() => {
    if (open) setOpen(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname]);

  const updatePosition = React.useCallback(() => {
    if (!open || !triggerRef.current || !ref.current) return;
    const triggerRect = triggerRef.current.getBoundingClientRect();
    const contentRect = ref.current.getBoundingClientRect();
    const padding = 8;
    const offset = 8;
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;

    let left = align === 'end' ? triggerRect.right - contentRect.width : triggerRect.left;
    left = Math.min(Math.max(left, padding), viewportWidth - contentRect.width - padding);

    let top = triggerRect.bottom + offset;
    if (top + contentRect.height > viewportHeight - padding) {
      top = triggerRect.top - contentRect.height - offset;
    }
    top = Math.min(Math.max(top, padding), viewportHeight - contentRect.height - padding);

    setStyles({
      position: 'fixed',
      top,
      left,
      minWidth: Math.max(170, Math.round(triggerRect.width))
    });
  }, [align, open, triggerRef]);

  React.useEffect(() => {
    if (!open) return;
    updatePosition();
    const onScroll = () => updatePosition();
    const onResize = () => updatePosition();
    window.addEventListener('scroll', onScroll, true);
    window.addEventListener('resize', onResize);
    return () => {
      window.removeEventListener('scroll', onScroll, true);
      window.removeEventListener('resize', onResize);
    };
  }, [open, updatePosition]);

  React.useEffect(() => {
    if (!open) return;
    const onDocClick = (e: MouseEvent) => {
      if (!ref.current || !triggerRef.current) return;
      const target = e.target;
      if (
        target instanceof Node &&
        !ref.current.contains(target) &&
        !triggerRef.current.contains(target)
      ) {
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
  }, [open, setOpen, triggerRef]);

  if (!open || !mounted) return null;

  return createPortal(
    <div
      ref={ref}
      style={styles}
      className={`z-[120] rounded-xl border border-white/15 bg-slate-950/95 p-1 shadow-2xl backdrop-blur ${className}`}
      role="menu"
    >
      {children}
    </div>,
    document.body
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
