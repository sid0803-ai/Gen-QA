import { api } from './client';
import type { AuthTokens, User } from './types';

export function register(email: string, password: string, fullName: string): Promise<User> {
  return api.post<User>(
    '/auth/register',
    { email, password, full_name: fullName },
    { skipAuth: true },
  );
}

/** Login uses the OAuth2 password flow: form-encoded, field name `username` for the email. */
export function login(email: string, password: string): Promise<AuthTokens> {
  return api.postForm<AuthTokens>(
    '/auth/login',
    { username: email, password },
    { skipAuth: true },
  );
}

export function me(): Promise<User> {
  return api.get<User>('/auth/me');
}
