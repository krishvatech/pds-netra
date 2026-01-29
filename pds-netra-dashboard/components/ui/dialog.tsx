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
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <button
        className="absolute inset-0 bg-slate-950/70 backdrop-blur-sm"
        onClick={() => {
          if (!isBusy) onCancel();
        }}
        disabled={isBusy}
        aria-label="Close dialog"
      />
      <div
        className="relative w-[92vw] max-w-lg glass-panel-strong rounded-2xl border border-white/10 p-6 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-dialog-title"
      >
        <div className="text-lg font-semibold font-display text-slate-100" id="confirm-dialog-title">
          {title}
        </div>
        {message && <div className="mt-2 text-sm text-slate-300">{message}</div>}
        <div className="mt-5 flex flex-wrap justify-end gap-2">
          <Button variant="outline" onClick={onCancel} disabled={isBusy}>
            {cancelLabel}
          </Button>
          <Button variant={confirmVariant} onClick={onConfirm} disabled={isBusy}>
            {isBusy ? 'Please wait...' : confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}
