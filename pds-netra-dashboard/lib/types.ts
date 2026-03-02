export type UserRole = 'STATE_ADMIN' | 'HQ_ADMIN' | 'DISTRICT_OFFICER' | 'GODOWN_MANAGER' | 'USER';

export type Severity = 'info' | 'warning' | 'critical';
export type AlertStatus = 'OPEN' | 'ACK' | 'CLOSED';
export type TestRunStatus = 'UPLOADED' | 'ACTIVE' | 'DEACTIVATED' | 'COMPLETED';

export interface LoginResponse {
  access_token?: string;
  token_type?: string;
  user: {
    id?: string;
    username: string;
    name?: string;
    role: UserRole;
    district?: string | null;
    godown_id?: string | null;
  };
}

export interface CreateGodownPayload {
  godown_id: string;
  name?: string | null;
  district?: string | null;
  code?: string | null;
}

export interface UpdateGodownPayload {
  name?: string | null;
  district?: string | null;
  code?: string | null;
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
  status?: 'OK' | 'ISSUES' | 'CRITICAL' | string | null;
}

export interface CameraInfo {
  camera_id: string;
  godown_id?: string | null;
  label?: string | null;
  role?: 'GATE_ANPR' | 'SECURITY' | 'HEALTH_ONLY' | string | null;
  rtsp_url?: string | null;
  is_active?: boolean | null;
  zones_json?: string | null;
  modules?: CameraModules | null;

  // Health hints (if backend provides)
  online?: boolean | null;
  last_frame_utc?: string | null;
  last_tamper_reason?: string | null;
}

export interface CameraModules {
  anpr_enabled?: boolean | null;
  gate_entry_exit_enabled?: boolean | null;
  person_after_hours_enabled?: boolean | null;
  animal_detection_enabled?: boolean | null;
  fire_detection_enabled?: boolean | null;
  health_monitoring_enabled?: boolean | null;
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
  movement_type?: 'AFTER_HOURS' | 'GENERIC' | 'UNPLANNED' | 'ODD_HOURS' | 'TALLY_MISMATCH' | 'NORMAL' | string | null;
  plate_text?: string | null;
  plate_norm?: string | null;
  direction?: string | null;
  match_status?: 'WHITELIST' | 'BLACKLIST' | 'UNKNOWN' | string | null;
  reason?: string | null;
  person_id?: string | null;
  person_name?: string | null;
  person_role?: string | null;
  match_score?: number | null;
  animal_species?: string | null;
  animal_label?: string | null;
  animal_count?: number | null;
  animal_confidence?: number | null;
  animal_is_night?: boolean | null;
  animal_bboxes?: number[][] | null;
  fire_classes?: string[] | null;
  fire_confidence?: number | null;
  fire_bboxes?: number[][] | null;
  fire_model_name?: string | null;
  fire_model_version?: string | null;
  fire_weights_id?: string | null;
  extra?: Record<string, unknown> | null;
  [key: string]: unknown;
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
    reason?: string | null;
    run_id?: string | null;
    person_id?: string | null;
    person_name?: string | null;
    match_score?: number | null;
    snapshot_url?: string | null;
    detected_count?: number | null;
    vehicle_plate?: string | null;
    occurred_at?: string | null;
    last_seen_at?: string | null;
    animal_species?: string | null;
    animal_label?: string | null;
    animal_count?: number | null;
    animal_confidence?: number | null;
    animal_is_night?: boolean | null;
    plate_norm?: string | null;
    plate_raw?: string | null;
    entry_at?: string | null;
    age_hours?: number | null;
    threshold_hours?: number | null;
    fire_confidence?: number | null;
    fire_classes?: string[] | null;
    fire_model_name?: string | null;
    fire_model_version?: string | null;
    fire_weights_id?: string | null;
    [key: string]: unknown;
  };
}

export interface AlertDetail extends AlertItem {
  linked_event_ids?: Array<string | number>;
  events?: EventItem[];
  actions?: AlertActionItem[];
}

export interface AlertDelivery {
  id: string;
  channel: string;
  target: string;
  status: 'PENDING' | 'SENT' | 'FAILED' | 'RETRYING' | string;
  attempts: number;
  next_retry_at?: string | null;
  last_error?: string | null;
  provider_message_id?: string | null;
  created_at: string;
  updated_at: string;
  sent_at?: string | null;
}

export interface NotificationEndpoint {
  id: string;
  scope: 'HQ' | 'GODOWN' | string;
  godown_id?: string | null;
  channel: 'WHATSAPP' | 'EMAIL' | string;
  target: string;
  is_enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface AlertReport {
  id: string;
  scope: string;
  period_start: string;
  period_end: string;
  generated_at: string;
  created_at: string;
  summary_json: Record<string, any>;
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
    after_hours_person_24h?: number | null;
    after_hours_vehicle_24h?: number | null;
    after_hours_person_7d?: number | null;
    after_hours_vehicle_7d?: number | null;
    animal_intrusions_24h?: number | null;
    animal_intrusions_7d?: number | null;
    open_gate_sessions?: number | null;
    fire_alerts_24h?: number | null;
    fire_alerts_7d?: number | null;
  };
  godowns: GodownListItem[];
}

export interface VehicleGateSession {
  id: string;
  godown_id: string;
  anpr_camera_id?: string | null;
  plate_raw: string;
  plate_norm: string;
  entry_at: string;
  exit_at?: string | null;
  status: 'OPEN' | 'CLOSED' | string;
  last_seen_at?: string | null;
  reminders_sent?: Record<string, string> | null;
  last_snapshot_url?: string | null;
  age_hours?: number | null;
  next_threshold_hours?: number | null;
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

export interface TestRunDetail extends TestRunItem { }

export interface MovementSummary {
  range?: { from?: string | null; to?: string | null };
  total_events: number;
  unique_plans: number;
  counts_by_type: Record<string, number>;
}

export interface MovementTimelinePoint {
  t: string;
  movement_type: string;
  count: number;
}

export interface DispatchIssueItem {
  id: number;
  godown_id: string;
  camera_id?: string | null;
  zone_id?: string | null;
  issue_time_utc: string;
  status: string;
  started_at_utc?: string | null;
  alerted_at_utc?: string | null;
  alert_id?: number | null;
}

export interface DispatchTraceItem {
  issue_id: number;
  godown_id: string;
  camera_id?: string | null;
  zone_id?: string | null;
  issue_time_utc: string;
  deadline_utc: string;
  status: string;
  alert_id?: number | null;
  started_at_utc?: string | null;
  alerted_at_utc?: string | null;
  first_movement_utc?: string | null;
  first_movement_type?: string | null;
  plan_id?: string | null;
  movement_count_24h: number;
  sla_met: boolean;
  delay_minutes?: number | null;
}

export interface RuleItem {
  id: number;
  godown_id: string;
  camera_id: string;
  zone_id: string;
  type: string;
  enabled: boolean;
  created_at?: string | null;
  updated_at?: string | null;
  start_time?: string | null;
  end_time?: string | null;
  start?: string | null;
  end?: string | null;
  threshold_seconds?: number | null;
  start_local?: string | null;
  end_local?: string | null;
  cooldown_seconds?: number | null;
  require_active_dispatch_plan?: boolean | null;
  allowed_overage_percent?: number | null;
  threshold_distance?: number | null;
  allowed_plates?: string[] | null;
  blocked_plates?: string[] | null;
}

export interface AfterHoursPolicy {
  id?: string | null;
  godown_id: string;
  timezone: string;
  day_start: string;
  day_end: string;
  presence_allowed: boolean;
  cooldown_seconds: number;
  enabled: boolean;
  source?: 'default' | 'override' | string;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface AfterHoursPolicyAudit {
  id: string;
  godown_id: string;
  actor?: string | null;
  source: string;
  changes: Record<string, { from: unknown; to: unknown }>;
  before?: Record<string, unknown> | null;
  after?: Record<string, unknown> | null;
  created_at?: string | null;
}

export interface AlertActionItem {
  id: number;
  alert_id: number;
  action_type: string;
  actor?: string | null;
  note?: string | null;
  created_at?: string | null;
}

export interface WatchlistPersonImage {
  id: string;
  image_url?: string | null;
  storage_path?: string | null;
  created_at?: string | null;
}

export interface WatchlistPerson {
  id: string;
  name: string;
  alias?: string | null;
  reason?: string | null;
  notes?: string | null;
  status: 'ACTIVE' | 'INACTIVE' | string;
  created_at?: string | null;
  updated_at?: string | null;
  images?: WatchlistPersonImage[];
}

export interface WatchlistMatchEvent {
  id: string;
  occurred_at: string;
  godown_id: string;
  camera_id: string;
  match_score: number;
  is_blacklisted: boolean;
  blacklist_person_id?: string | null;
  snapshot_url?: string | null;
  storage_path?: string | null;
  correlation_id?: string | null;
  created_at?: string | null;
}

export interface AuthorizedUserItem {
  person_id: string;
  name: string;
  role?: string | null;
  godown_id?: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CreateAuthorizedUserPayload {
  person_id: string;
  name: string;
  role?: string | null;
  godown_id?: string | null;
  is_active?: boolean;
}

export interface UpdateAuthorizedUserPayload {
  name?: string | null;
  role?: string | null;
  godown_id?: string | null;
  is_active?: boolean;
}

export interface AnprEvent {
  timestamp_utc: string;
  timestamp_local: string;
  camera_id: string;
  zone_id?: string | null;
  plate_text: string;
  match_status: string;
  event_type: string;
  confidence: number;
  bbox?: any;
}

export interface AnprEventsResponse {
  source: { db: boolean; table: string };
  count: number;
  events: AnprEvent[];
}

export interface AnprVehicle {
  id: string;
  godown_id: string;
  plate_raw: string;
  plate_norm: string;
  list_type?: 'WHITELIST' | 'BLACKLIST' | string | null;
  transporter?: string | null;
  notes?: string | null;
  is_active: boolean;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface AnprVehicleListResponse {
  items: AnprVehicle[];
  total: number;
  page: number;
  page_size: number;
}

export interface AnprDailyPlan {
  id: string;
  godown_id: string;
  plan_date: string; // YYYY-MM-DD
  timezone_name: string;
  expected_count?: number | null;
  cutoff_time_local: string; // HH:MM:SS
  notes?: string | null;
}

export type AnprPlanStatus = 'PLANNED' | 'ARRIVED' | 'DELAYED' | 'CANCELLED' | 'NO_SHOW' | string;

export interface AnprDailyPlanItem {
  id: string;
  plan_id: string;
  vehicle_id?: string | null;
  plate_raw: string;
  plate_norm: string;
  expected_by_local?: string | null; // HH:MM:SS
  status?: AnprPlanStatus | null; // manual
  notes?: string | null;
  effective_status: AnprPlanStatus;
  arrived_at_utc?: string | null;
}

export interface AnprDailyPlanResponse {
  plan: AnprDailyPlan;
  items: AnprDailyPlanItem[];
}

export interface AnprDailyReportRow {
  date_local: string; // YYYY-MM-DD
  expected_count?: number | null;
  planned_items: number;
  arrived: number;
  delayed: number;
  no_show: number;
  cancelled: number;
}

export interface AnprDailyReportResponse {
  godown_id: string;
  timezone_name: string;
  rows: AnprDailyReportRow[];
}

export interface CsvImportRowResult {
  row_number: number;
  plate_text: string;
  status: string;
  message?: string | null;
  entity_id?: string | null;
}

export interface CsvImportSummary {
  total: number;
  created: number;
  updated: number;
  skipped: number;
  failed: number;
  rows: CsvImportRowResult[];
}
