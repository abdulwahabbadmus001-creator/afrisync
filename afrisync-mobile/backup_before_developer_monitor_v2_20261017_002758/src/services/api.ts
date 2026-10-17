import { getApiBaseUrl } from '../config/env';
import type { ApiResult, UserSession } from '../types';

async function request<T>(path: string, options: RequestInit = {}): Promise<ApiResult<T>> {
  const baseUrl = await getApiBaseUrl();
  const url = `${baseUrl}${path.startsWith('/') ? path : `/${path}`}`;
  try {
    const response = await fetch(url, {
      ...options,
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
        ...(options.headers || {})
      }
    });

    const text = await response.text();
    const payload = text ? JSON.parse(text) : null;
    if (!response.ok) {
      return { ok: false, error: payload?.detail || payload?.message || `Request failed: ${response.status}` };
    }
    return { ok: true, data: payload as T };
  } catch (error) {
    return { ok: false, error: error instanceof Error ? error.message : 'Network request failed' };
  }
}

function normalizeSession(payload: any): UserSession {
  const user = payload.user || payload;
  return {
    userId: String(user.user_id || user.id || payload.user_id || payload.id || ''),
    username: String(user.username || payload.username || user.email || 'mobile-user'),
    email: user.email || payload.email,
    fullName: user.full_name || user.fullName || payload.full_name || payload.fullName,
    syncToken: String(payload.sync_token || payload.token || payload.access_token || payload.session_token || '')
  };
}

export async function loginWithPassword(identifier: string, password: string): Promise<ApiResult<UserSession>> {
  const result = await request<any>('/login', {
    method: 'POST',
    body: JSON.stringify({ username: identifier, identifier, email: identifier, password })
  });
  if (!result.ok || !result.data) return { ok: false, error: result.error || 'Login failed' };
  return { ok: true, data: normalizeSession(result.data) };
}

export async function registerAccount(input: {
  fullName: string;
  email: string;
  username: string;
  password: string;
}): Promise<ApiResult<{ message: string; verificationRequired?: boolean }>> {
  return request('/register', {
    method: 'POST',
    body: JSON.stringify({
      full_name: input.fullName,
      fullName: input.fullName,
      email: input.email,
      username: input.username,
      password: input.password
    })
  });
}

export async function verifyEmail(email: string, code: string): Promise<ApiResult<{ message: string }>> {
  return request('/auth/verify-email', {
    method: 'POST',
    body: JSON.stringify({ email, code })
  });
}

export async function resendVerification(email: string): Promise<ApiResult<{ message: string }>> {
  return request('/auth/resend-verification', {
    method: 'POST',
    body: JSON.stringify({ email })
  });
}

export async function requestPasswordReset(identifier: string): Promise<ApiResult<{ message: string }>> {
  return request('/auth/request-password-reset', {
    method: 'POST',
    body: JSON.stringify({ identifier, email: identifier, username: identifier })
  });
}

export async function resetPassword(input: {
  identifier: string;
  codeOrToken: string;
  newPassword: string;
}): Promise<ApiResult<{ message: string }>> {
  return request('/auth/reset-password', {
    method: 'POST',
    body: JSON.stringify({
      identifier: input.identifier,
      token: input.codeOrToken,
      code: input.codeOrToken,
      new_password: input.newPassword,
      newPassword: input.newPassword
    })
  });
}

export async function pushSyncItem(token: string, entityType: string, payload: any): Promise<ApiResult<any>> {
  const endpoint = entityType === 'note' ? '/sync/notes' : '/sync/projects';
  return request(endpoint, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify(payload)
  });
}

export async function pullRemoteProjects(token: string): Promise<ApiResult<any[]>> {
  return request('/sync/projects', {
    method: 'GET',
    headers: { Authorization: `Bearer ${token}` }
  });
}

export async function healthCheck(): Promise<ApiResult<{ status?: string; service?: string }>> {
  return request('/health', { method: 'GET' });
}
