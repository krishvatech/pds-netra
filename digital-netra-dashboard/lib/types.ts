export type User = {
  id: string;
  username: string;
  email: string;
  phone?: string | null;
  is_admin: boolean;
  is_active: boolean;
  created_at: string;
};

export type LoginResponse = {
  access_token: string;
  token_type: 'bearer';
  user: User;
};

export type SessionResponse = {
  user: User | null;
};

export type UsernameCheckResponse = {
  username: string;
  available: boolean;
};

export type EmailCheckResponse = {
  email: string;
  available: boolean;
};

export interface Camera {
  id: string;
  camera_name: string;
  role: string;
  rtsp_url: string;
  is_active: boolean;
  user_id: string;
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
