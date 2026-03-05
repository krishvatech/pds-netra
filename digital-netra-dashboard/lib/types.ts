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
