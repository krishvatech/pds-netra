export type User = {
  id: string;
  email: string;
  phone?: string | null;
  is_admin: boolean;
  is_active: boolean;
  created_at: string;
  first_name: string;
  last_name: string;
};

export type LoginResponse = {
  access_token: string;
  token_type: 'bearer';
  user: User;
};

export type SessionResponse = {
  user: SessionUser | null;
};

export type SessionUser = {
  id: string;
  email: string;
  is_admin: boolean;
  is_active: boolean;
};

export type EmailCheckResponse = {
  email: string;
  available: boolean;
};

export type PasswordVerifyResponse = {
  valid: boolean;
};

export interface Camera {
  id: string;
  camera_name: string;
  role: string;
  rtsp_url: string;
  is_active: boolean;
  approval_status: string;
  user_id: string;
  owner_first_name?: string | null;
  owner_last_name?: string | null;
  edge_id?: string | null;
  created_at: string;
  updated_at: string;
}

export interface CameraCreate {
  camera_name: string;
  role: string;
  rtsp_url: string;
  is_active: boolean;
}

export interface CameraUpdate {
  camera_name?: string;
  role?: string;
  rtsp_url?: string;
  is_active?: boolean;
}

export interface EdgeDevice {
  id: string;
  name: string;
  api_key: string;
  is_active: boolean;
  location: string;
  ip: string;
  user_id: string;
  created_at: string;
  updated_at: string;
}

export interface EdgeDeviceCreate {
  name: string;
  api_key: string;
  is_active: boolean;
  location: string;
  ip: string;
  password: string;
  user_id: string;
}

export interface EdgeDeviceUpdate {
  name?: string;
  api_key?: string;
  is_active?: boolean;
  location?: string;
  ip?: string;
  password?: string;
  user_id?: string;
}

export interface RuleType {
  id: string;
  rule_type_name: string;
  rule_type_slug: string;
  model_name: string;
  created_at: string;
  updated_at: string;
}

export interface RuleTypeCreate {
  rule_type_name: string;
  rule_type_slug: string;
  model_name: string;
}

export interface RuleTypeUpdate {
  rule_type_name: string;
  rule_type_slug: string;
  model_name: string;
}

export interface UserRuleType {
  id: string;
  user_id: string;
  rule_type_id: string;
  created_at: string;
  updated_at: string;
}
