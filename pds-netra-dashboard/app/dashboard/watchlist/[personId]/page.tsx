'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import type { WatchlistMatchEvent, WatchlistPerson } from '@/lib/types';
import { addWatchlistImages, deactivateWatchlistPerson, getWatchlistMatches, getWatchlistPerson } from '@/lib/api';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { WatchlistMatchesTable } from '@/components/tables/WatchlistMatchesTable';


export default function WatchlistPersonDetailPage() {
  const params = useParams<{ personId: string }>();
  const personId = params.personId;

  const [person, setPerson] = useState<WatchlistPerson | null>(null);
  const [matches, setMatches] = useState<WatchlistMatchEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [files, setFiles] = useState<FileList | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [fileError, setFileError] = useState<string | null>(null);
  const inlineErrorClass = 'text-xs text-red-400';
  const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;
  const maxUploadMb = (MAX_UPLOAD_BYTES / (1024 * 1024)).toFixed(1);

  function friendlyWatchlistError(): string {
    return 'Check your network and try again.';
  }

  useEffect(() => {
    let mounted = true;
    (async () => {
      setError(null);
      try {
        const [personResp, matchesResp] = await Promise.all([
          getWatchlistPerson(personId),
          getWatchlistMatches(personId, { page: 1, page_size: 50 })
        ]);
        if (mounted) {
          setPerson(personResp);
          setMatches(matchesResp.items ?? []);
        }
      } catch (e) {
        if (mounted) setError(friendlyWatchlistError());
      }
    })();
    return () => { mounted = false; };
  }, [personId]);

  async function handleDeactivate() {
    if (!person) return;
    try {
      const updated = await deactivateWatchlistPerson(person.id);
      setPerson(updated);
    } catch (e) {
      setError('Unable to deactivate right now; please try again.');
    }
  }

  async function handleAddImages() {
    if (!files || !person) return;
    setIsSaving(true);
    try {
      const formData = new FormData();
      Array.from(files).forEach((file) => formData.append('reference_images', file));
      const updated = await addWatchlistImages(person.id, formData);
      setPerson(updated);
      setFiles(null);
      setFileError(null);
    } catch (e) {
      setError(`Upload failed. Please use images smaller than ${maxUploadMb} MB and try again.`);
    } finally {
      setIsSaving(false);
    }
  }

  if (!person) {
    return (
      <div className="space-y-4">
        {error && <p className={inlineErrorClass}>{error}</p>}
        <div className="text-sm text-slate-500">Loading...</div>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {error && <p className={inlineErrorClass}>{error}</p>}

      <Card className="hud-card">
        <CardHeader>
          <div className="text-lg font-semibold font-display">Watchlist Profile</div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <div className="text-xs text-slate-400 uppercase tracking-[0.3em]">Name</div>
              <div className="text-lg font-semibold text-slate-100">{person.name}</div>
              <div className="text-xs text-slate-500">{person.id}</div>
            </div>
            <div>
              <div className="text-xs text-slate-400 uppercase tracking-[0.3em]">Alias</div>
              <div className="text-slate-100">{person.alias ?? '-'}</div>
            </div>
            <div>
              <div className="text-xs text-slate-400 uppercase tracking-[0.3em]">Status</div>
              <div className="text-slate-100">{person.status}</div>
            </div>
          </div>
          {person.reason && (
            <div className="mt-4">
              <div className="text-xs text-slate-400 uppercase tracking-[0.3em]">Reason</div>
              <div className="text-slate-100">{person.reason}</div>
            </div>
          )}
          {person.notes && (
            <div className="mt-4">
              <div className="text-xs text-slate-400 uppercase tracking-[0.3em]">Notes</div>
              <div className="text-slate-100">{person.notes}</div>
            </div>
          )}
          {person.images && person.images.length > 0 && (
            <div className="mt-4">
              <div className="text-xs text-slate-400 uppercase tracking-[0.3em]">Reference images</div>
              <div className="mt-2 grid grid-cols-2 md:grid-cols-4 gap-2">
                {person.images.map((img) => (
                  <a
                    key={img.id}
                    href={img.image_url ?? img.storage_path ?? '#'}
                    target="_blank"
                    rel="noreferrer"
                    className="block rounded-lg border border-white/10 bg-white/5 p-2 text-xs text-slate-300 hover:border-amber-400"
                  >
                    {img.image_url ?? img.storage_path ?? 'Image'}
                  </a>
                ))}
              </div>
            </div>
          )}
          <div className="mt-6 flex flex-wrap items-center gap-3">
            <Button variant="outline" onClick={handleDeactivate}>Deactivate</Button>
            <div className="flex items-center gap-3">
              <Label>Upload images</Label>
              <div className="flex flex-col">
                <Input
                  type="file"
                  multiple
                  onChange={(e) => {
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
                <p className={inlineErrorClass}>Max image size: {maxUploadMb} MB</p>
                {fileError && <p className={`${inlineErrorClass} mt-1`}>{fileError}</p>}
              </div>
              <Button onClick={handleAddImages} disabled={!files || isSaving}>{isSaving ? 'Uploading...' : 'Upload'}</Button>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card className="hud-card">
        <CardHeader>
          <div className="text-lg font-semibold font-display">Matches Timeline</div>
        </CardHeader>
        <CardContent>
          <WatchlistMatchesTable matches={matches} />
        </CardContent>
      </Card>
    </div>
  );
}
