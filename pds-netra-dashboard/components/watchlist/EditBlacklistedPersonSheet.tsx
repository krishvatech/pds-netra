'use client';

import { useEffect, useMemo, useState } from 'react';
import type { WatchlistPerson } from '@/lib/types';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { Separator } from '@/components/ui/separator';
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet';

export type EditBlacklistedPersonPayload = {
  name: string;
  alias: string;
  reason: string;
  notes: string;
  status: string;
  referenceImages: FileList | null;
};

type EditBlacklistedPersonSheetProps = {
  open: boolean;
  person: WatchlistPerson | null;
  isSaving: boolean;
  error: string | null;
  maxUploadMb: string;
  onOpenChange: (open: boolean) => void;
  onSave: (payload: EditBlacklistedPersonPayload) => Promise<void>;
  onClearError: () => void;
};

export function EditBlacklistedPersonSheet({
  open,
  person,
  isSaving,
  error,
  maxUploadMb,
  onOpenChange,
  onSave,
  onClearError
}: EditBlacklistedPersonSheetProps) {
  const [form, setForm] = useState({
    name: '',
    alias: '',
    reason: '',
    notes: '',
    status: 'ACTIVE'
  });
  const [files, setFiles] = useState<FileList | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);

  const MAX_UPLOAD_BYTES = useMemo(() => Number(maxUploadMb) * 1024 * 1024, [maxUploadMb]);

  useEffect(() => {
    if (!person || !open) return;
    setForm({
      name: person.name ?? '',
      alias: person.alias ?? '',
      reason: person.reason ?? '',
      notes: person.notes ?? '',
      status: person.status ?? 'ACTIVE'
    });
    setFiles(null);
    setFileError(null);
    onClearError();
  }, [person, open, onClearError]);

  if (!person) return null;

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="overflow-hidden">
        <SheetHeader>
          <SheetTitle>Edit Blacklisted Person</SheetTitle>
          <SheetDescription>Update profile details, status, and optional reference images.</SheetDescription>
        </SheetHeader>
        <div className="h-[calc(100%-88px)] overflow-auto p-4">
          <div className="space-y-4">
            <div>
              <Label>Name</Label>
              <Input
                value={form.name}
                onChange={(e) => {
                  onClearError();
                  setForm((prev) => ({ ...prev, name: e.target.value }));
                }}
              />
            </div>
            <div>
              <Label>Alias</Label>
              <Input
                value={form.alias}
                onChange={(e) => {
                  onClearError();
                  setForm((prev) => ({ ...prev, alias: e.target.value }));
                }}
              />
            </div>
            <div>
              <Label>Reason</Label>
              <Input
                value={form.reason}
                onChange={(e) => {
                  onClearError();
                  setForm((prev) => ({ ...prev, reason: e.target.value }));
                }}
              />
            </div>
            <div>
              <Label>Notes</Label>
              <Textarea
                value={form.notes}
                onChange={(e) => {
                  onClearError();
                  setForm((prev) => ({ ...prev, notes: e.target.value }));
                }}
              />
            </div>
            <div>
              <Label>Status</Label>
              <Select
                value={form.status}
                onChange={(e) => {
                  onClearError();
                  setForm((prev) => ({ ...prev, status: e.target.value }));
                }}
                options={[
                  { label: 'Active', value: 'ACTIVE' },
                  { label: 'Inactive', value: 'INACTIVE' }
                ]}
              />
            </div>
            <div>
              <Label>Reference images (optional)</Label>
              <Input
                type="file"
                multiple
                onChange={(e) => {
                  onClearError();
                  const selected = e.target.files;
                  if (!selected) {
                    setFiles(null);
                    setFileError(null);
                    return;
                  }
                  const oversized = Array.from(selected).find((file) => file.size > MAX_UPLOAD_BYTES);
                  if (oversized) {
                    setFiles(null);
                    setFileError(
                      `File too large (${(oversized.size / 1024 / 1024).toFixed(1)} MB). Max ${maxUploadMb} MB allowed.`
                    );
                    return;
                  }
                  setFiles(selected);
                  setFileError(null);
                }}
              />
              <p className="mt-1 text-xs text-slate-400">Max image size: {maxUploadMb} MB</p>
              {fileError && <p className="mt-1 text-xs text-red-400">{fileError}</p>}
            </div>
            {error && <p className="text-xs text-red-400">{error}</p>}
            <Separator className="border-white/10" />
            <div className="flex justify-end gap-2">
              <Button
                variant="outline"
                onClick={() => onOpenChange(false)}
                disabled={isSaving}
                className="border-white/10 bg-white/5 text-slate-200 hover:bg-white/10"
              >
                Cancel
              </Button>
              <Button
                onClick={() =>
                  void onSave({
                    name: form.name,
                    alias: form.alias,
                    reason: form.reason,
                    notes: form.notes,
                    status: form.status,
                    referenceImages: files
                  })
                }
                disabled={isSaving}
              >
                {isSaving ? 'Saving...' : 'Save changes'}
              </Button>
            </div>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}
