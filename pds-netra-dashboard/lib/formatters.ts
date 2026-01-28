import type { Severity } from './types';

export function formatUtc(ts?: string | null): string {
  if (!ts) return '-';
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return ts;
  return d.toLocaleString(undefined, { year: 'numeric', month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit' });
}

export function humanEventType(eventType: string): string {
  const map: Record<string, string> = {
    UNAUTH_PERSON: 'Unauthorized Person',
    FACE_UNKNOWN_ACCESS: 'Unauthorized Person',
    LOITERING: 'Loitering',
    ANIMAL_INTRUSION: 'Animal Intrusion',
    BAG_MOVEMENT: 'Bag/Trolley Movement',
    ANPR_PLATE_DETECTED: 'ANPR Plate Detected',
    ANPR_PLATE_MISMATCH: 'ANPR Plate Mismatch',
    CAMERA_TAMPERED: 'Camera Tampered',
    CAMERA_OFFLINE: 'Camera Offline',
    LOW_LIGHT: 'Low Light'
  };
  return map[eventType] ?? eventType.replaceAll('_', ' ');
}

export function humanAlertType(alertType: string): string {
  const map: Record<string, string> = {
    SECURITY_UNAUTH_ACCESS: 'Security: Unauthorized Access',
    OPERATION_BAG_MOVEMENT_ANOMALY: 'Operations: Bag Movement Anomaly',
    OPERATION_UNPLANNED_MOVEMENT: 'Operations: Unplanned Movement',
    CAMERA_HEALTH_ISSUE: 'Camera Health Issue',
    ANPR_MISMATCH_VEHICLE: 'ANPR Vehicle Mismatch',
    ANIMAL_INTRUSION: 'Animal Intrusion',
    DISPATCH_NOT_STARTED_24H: 'Dispatch: Not Started in 24h'
  };
  return map[alertType] ?? alertType.replaceAll('_', ' ');
}

export function severityBadge(sev: Severity): { label: string; className: string } {
  if (sev === 'critical') return { label: 'Critical', className: 'bg-red-100 text-red-800 border-red-200' };
  if (sev === 'warning') return { label: 'Warning', className: 'bg-amber-100 text-amber-800 border-amber-200' };
  return { label: 'Info', className: 'bg-slate-100 text-slate-800 border-slate-200' };
}

export function severityBadgeClass(sev: Severity): string {
  if (sev === 'critical') return 'sev-critical';
  if (sev === 'warning') return 'sev-warning';
  return 'sev-info';
}
