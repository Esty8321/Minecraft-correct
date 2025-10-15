export interface User {
  id: string;
  username: string;
  email: string;
}

export interface RegisterRequest {
  username: string;
  email: string;
}

export interface LoginRequest {
  username?: string;
  email?: string;
}

export interface AuthResponse {
  ok: boolean;
  user: User;
  token?: string;
  player_id:string
}

export interface RegisterResponse {
  ok: boolean;
  user: User;
}