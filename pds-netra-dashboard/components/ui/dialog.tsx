'use client';

import { useEffect, useMemo, useState, type ReactElement, type ReactNode } from 'react';
import * as Popover from '@radix-ui/react-popover';
import { Button } from './button';

type Variant = 'default' | 'outline' | 'ghost' | 'danger';

type ConfirmDialogProps = {
  open: boolean;
  title: string;
  message?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  confirmVariant?: Variant;
  isBusy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
};

export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  confirmVariant = 'default',
  isBusy = false,
  onConfirm,
  onCancel
}: ConfirmDialogProps) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !isBusy) onCancel();
    };
    document.addEventListener('keydown', onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = prev;
    };
  }, [open, onCancel, isBusy]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button
        className="absolute inset-0 bg-slate-950/80 backdrop-blur-md"
        onClick={() => {
          if (!isBusy) onCancel();
        }}
        disabled={isBusy}
        aria-label="Close dialog"
      />
      <div
        className="relative w-full max-w-[95vw] sm:max-w-md max-h-[85vh] hud-card overflow-hidden animate-fade-up border border-white/10 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-dialog-title"
      >
        <div className="max-h-[85vh] overflow-y-auto p-6 sm:p-8">
          <div className="text-xl font-semibold font-display text-white" id="confirm-dialog-title">
            {title}
          </div>
          {message && <div className="mt-3 text-sm text-slate-400 leading-relaxed">{message}</div>}
          <div className="mt-8 flex flex-col-reverse sm:flex-row justify-end gap-3">
            <Button
              variant="outline"
              onClick={onCancel}
              disabled={isBusy}
              className="!bg-white/5 !border-white/10 !text-slate-300 hover:!bg-white/10 hover:!text-white border-0"
            >
              {cancelLabel}
            </Button>
            <Button
              variant={confirmVariant}
              onClick={onConfirm}
              disabled={isBusy}
              className="min-w-[100px]"
            >
              {isBusy ? 'Wait...' : confirmLabel}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

type ConfirmDeletePopoverProps = {
  title: string;
  description?: ReactNode;
  confirmText?: string;
  cancelText?: string;
  confirmVariant?: Variant;
  disabled?: boolean;
  confirmDisabled?: boolean;
  isBusy?: boolean;
  onConfirm: () => void | Promise<void>;
  onOpenChange?: (open: boolean) => void;
  children: ReactElement;
};

export function ConfirmDeletePopover({
  title,
  description,
  confirmText = 'Delete',
  cancelText = 'Cancel',
  confirmVariant = 'danger',
  disabled = false,
  confirmDisabled = false,
  isBusy = false,
  onConfirm,
  onOpenChange,
  children
}: ConfirmDeletePopoverProps) {
  const [open, setOpen] = useState(false);
  const busy = disabled || isBusy;
  const blocked = confirmDisabled || busy;

  const trigger = useMemo(() => {
    if (!children) return null;
    return children;
  }, [children]);

  async function handleConfirm() {
    if (blocked) return;
    try {
      await onConfirm();
      setOpen(false);
      onOpenChange?.(false);
    } catch {
      // Keep open on failure.
    }
  }

  if (!trigger) return null;

  const triggerNode = (
    <span
      onClick={(e) => {
        if (busy) return;
        setOpen(true);
        e.stopPropagation();
      }}
      onKeyDown={(e) => {
        if (busy) return;
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          setOpen(true);
        }
      }}
      className="inline-flex"
      aria-haspopup="dialog"
      aria-expanded={open}
    >
      {trigger}
    </span>
  );

  return (
    <Popover.Root
      open={open}
      onOpenChange={(next) => {
        if (busy) return;
        setOpen(next);
        onOpenChange?.(next);
      }}
    >
      <Popover.Anchor asChild>
        {triggerNode}
      </Popover.Anchor>
      <Popover.Portal>
        <Popover.Content
          side="top"
          align="end"
          sideOffset={8}
          collisionPadding={16}
          className="z-[9999] min-w-[260px] max-w-[calc(100vw-2rem)] rounded-xl border border-white/10 bg-slate-950/95 p-4 text-slate-100 shadow-2xl"
          onOpenAutoFocus={(e) => e.preventDefault()}
          onEscapeKeyDown={() => !busy && setOpen(false)}
        >
          <div className="text-sm font-semibold text-white">{title}</div>
          {description ? <div className="mt-2 text-xs text-slate-400">{description}</div> : null}
          <div className="mt-4 flex flex-col-reverse sm:flex-row justify-end gap-2">
            <Button
              variant="outline"
              onClick={() => setOpen(false)}
              disabled={busy}
              className="!bg-white/5 !border-white/10 !text-slate-300 hover:!bg-white/10 hover:!text-white border-0"
            >
              {cancelText}
            </Button>
            <Button
              variant={confirmVariant}
              onClick={handleConfirm}
              disabled={blocked}
              className="min-w-[100px]"
            >
              {isBusy ? 'Wait...' : confirmText}
            </Button>
          </div>
          <Popover.Arrow className="fill-slate-950/95" />
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
