export type UserRole = 'STATE_ADMIN' | 'DISTRICT_OFFICER' | 'GODOWN_MANAGER';

export type Severity = 'info' | 'warning' | 'critical';
export type AlertStatus = 'OPEN' | 'CLOSED';
export type TestRunStatus = 'UPLOADED' | 'ACTIVE' | 'DEACTIVATED' | 'COMPLETED';

export interface LoginResponse {
  access_token: string;
  token_type?: string;
  user: {
    username: string;
    name?: string;
    role: UserRole;
    district?: string | null;
    godown_id?: string | null;
  };
}

export interface GodownListItem {
  godown_id: string;
  name?: string | null;
  district?: string | null;
  capacity?: number | null;

  // Optional summary fields (if backend provides)
  cameras_total?: number | null;
  cameras_online?: number | null;
  cameras_offline?: number | null;
  open_alerts_total?: number | null;
  open_alerts_warning?: number | null;
  open_alerts_critical?: number | null;
  last_event_time_utc?: string | null;
}

export interface CameraInfo {
  camera_id: string;
  label?: string | null;
  role?: 'GATE' | 'AISLE' | 'PERIMETER' | string | null;
  zones_json?: string | null;

  // Health hints (if backend provides)
  online?: boolean | null;
  last_frame_utc?: string | null;
  last_tamper_reason?: string | null;
}

export interface GodownDetail {
  godown_id: string;
  name?: string | null;
  district?: string | null;
  capacity?: number | null;
  cameras: CameraInfo[];
  summary?: {
    alerts_last_24h?: number | null;
    critical_alerts_last_24h?: number | null;
    last_event_time_utc?: string | null;
  };
}

export interface EventMeta {
  zone_id?: string | null;
  rule_id?: string | null;
  confidence?: number | null;
  movement_type?: 'AFTER_HOURS' | 'GENERIC' | 'UNPLANNED' | string | null;
  plate_text?: string | null;
  match_status?: 'WHITELIST' | 'BLACKLIST' | 'UNKNOWN' | string | null;
  reason?: string | null;
  person_id?: string | null;
  person_name?: string | null;
  person_role?: string | null;
  extra?: Record<string, unknown> | null;
}

export interface EventItem {
  id?: number | string;
  event_id: string;
  godown_id: string;
  camera_id: string;
  event_type: string;
  severity: Severity;
  timestamp_utc: string;
  bbox?: [number, number, number, number] | null;
  track_id?: number | null;
  image_url?: string | null;
  clip_url?: string | null;
  meta: EventMeta;
}

export interface AlertItem {
  id: string;
  godown_id: string;
  godown_name?: string | null;
  district?: string | null;
  camera_id?: string | null;
  alert_type: string;
  severity_final: Severity;
  status: AlertStatus;
  start_time: string;
  end_time?: string | null;
  summary?: string | null;
  count_events?: number | null;

  // Useful hints
  key_meta?: {
    zone_id?: string | null;
    plate_text?: string | null;
    movement_type?: string | null;
    run_id?: string | null;
  };
}

export interface AlertDetail extends AlertItem {
  linked_event_ids?: Array<string | number>;
  events?: EventItem[];
}

export interface HealthSummary {
  timestamp_utc?: string | null;
  godowns_with_issues: number;
  cameras_offline: number;
  recent_health_events?: EventItem[];
  recent_camera_status?: Array<{
    godown_id: string;
    camera_id: string;
    online: boolean;
    last_frame_utc?: string | null;
    last_tamper_reason?: string | null;
  }>;
  mqtt_consumer?: {
    enabled: boolean;
    connected: boolean;
  };
}

export interface GodownHealth {
  godown_id: string;
  timestamp_utc?: string | null;
  cameras: Array<{
    camera_id: string;
    online: boolean;
    last_frame_utc?: string | null;
    last_tamper_reason?: string | null;
  }>;
}

export interface Paginated<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface OverviewData {
  timestamp_utc?: string | null;
  stats: {
    godowns_monitored: number;
    open_alerts_critical: number;
    open_alerts_warning: number;
    cameras_with_issues: number;
    alerts_by_type: Record<string, number>;
    alerts_over_time: Array<{ t: string; count: number }>;
  };
  godowns: GodownListItem[];
}

export interface TestRunItem {
  run_id: string;
  godown_id: string;
  camera_id: string;
  zone_id?: string | null;
  run_name?: string | null;
  status: TestRunStatus;
  created_at?: string | null;
  updated_at?: string | null;
  activated_at?: string | null;
  deactivated_at?: string | null;
  completed_at?: string | null;
  saved_path?: string | null;
  config_path?: string | null;
  override_path?: string | null;
  events_count?: number | null;
}

export interface TestRunDetail extends TestRunItem {}
