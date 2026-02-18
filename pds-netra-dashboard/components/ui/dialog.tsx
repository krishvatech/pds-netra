'use client';

import { useEffect } from 'react';
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
