import { getApiBaseUrl, normalizeApiUrl } from '../config/env';
import type { ApiResult, DeveloperApiKey, DeveloperEvent, DeveloperProject, UserSession } from '../types';

async function request<T>(path: string, options: RequestInit = {}, overrideBaseUrl?: string): Promise<ApiResult<T>> {
  const base = normalizeApiUrl(overrideBaseUrl || await getApiBaseUrl());
  if (!base) return { ok: false, error: 'AfriSync backend is not configured.' };
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 12000);
  try {
    const response = await fetch(`${base}${path}`, {
      ...options,
      signal: controller.signal,
      headers: { 'Content-Type': 'application/json', ...(options.headers || {}) }
    });
    const text = await response.text();
    let payload: any = null;
    try { payload = text ? JSON.parse(text) : null; } catch { payload = text; }
    if (!response.ok) {
      const detail = typeof payload === 'object' ? payload?.detail || payload?.message : payload;
      return { ok: false, status: response.status, error: String(detail || `Request failed (${response.status})`), detail: payload };
    }
    return { ok: true, status: response.status, data: payload as T };
  } catch (error: any) {
    const message = error?.name === 'AbortError' ? 'Connection timed out.' : error?.message || 'Network request failed.';
    return { ok: false, error: message };
  } finally {
    clearTimeout(timeout);
  }
}

function normalizeSession(payload: any): UserSession {
  return {
    userId: String(payload?.user_id || payload?.id || ''),
    username: String(payload?.username || payload?.email || ''),
    email: payload?.email || undefined,
    fullName: payload?.full_name || undefined,
    syncToken: String(payload?.sync_token || ''),
    syncTokenExpiresAt: payload?.sync_token_expires_at || undefined
  };
}

function authHeaders(token: string): Record<string, string> { return { Authorization: `Bearer ${token}` }; }

export async function testBackendUrl(url: string): Promise<ApiResult<any>> { return request('/health', { method: 'GET' }, url); }
export async function healthCheck(): Promise<ApiResult<any>> { return request('/health', { method: 'GET' }); }

export async function loginWithPassword(identifier: string, password: string): Promise<ApiResult<UserSession>> {
  const result = await request<any>('/login', { method: 'POST', body: JSON.stringify({ username: identifier.trim(), password }) });
  if (!result.ok || !result.data) return result as ApiResult<UserSession>;
  const session = normalizeSession(result.data);
  if (!session.userId || !session.syncToken) return { ok: false, error: 'Server login response did not contain a valid session token.' };
  return { ...result, data: session };
}

export type RegisterResponse = { message: string; verificationRequired: boolean; identifier: string; developmentVerificationCode?: string; session?: UserSession };

export async function registerAccount(input: { fullName: string; email: string; username: string; password: string }): Promise<ApiResult<RegisterResponse>> {
  const result = await request<any>('/register', {
    method: 'POST',
    body: JSON.stringify({ full_name: input.fullName.trim(), email: input.email.trim(), username: input.username.trim(), password: input.password })
  });
  if (!result.ok || !result.data) return result as ApiResult<RegisterResponse>;
  const verificationRequired = Boolean(result.data.verification_required);
  return {
    ...result,
    data: {
      message: result.data.message || 'Account created.',
      verificationRequired,
      identifier: result.data.email || result.data.username || input.email,
      developmentVerificationCode: result.data.development_verification_code || undefined,
      session: !verificationRequired && result.data.sync_token ? normalizeSession(result.data) : undefined
    }
  };
}

export async function verifyEmail(identifier: string, code: string): Promise<ApiResult<UserSession>> {
  const result = await request<any>('/email-verification/confirm', { method: 'POST', body: JSON.stringify({ username_or_email: identifier.trim(), code: code.trim() }) });
  if (!result.ok || !result.data) return result as ApiResult<UserSession>;
  const session = normalizeSession(result.data);
  if (!session.userId || !session.syncToken) return { ok: false, error: 'Verification succeeded but no session token was returned.' };
  return { ...result, data: session };
}

export async function resendVerification(identifier: string): Promise<ApiResult<any>> {
  return request('/email-verification/resend', { method: 'POST', body: JSON.stringify({ username_or_email: identifier.trim() }) });
}

export async function requestPasswordReset(identifier: string): Promise<ApiResult<any>> {
  return request('/password-reset/request', { method: 'POST', body: JSON.stringify({ username: identifier.trim() }) });
}

export async function resetPassword(token: string, newPassword: string): Promise<ApiResult<any>> {
  return request('/password-reset/confirm', { method: 'POST', body: JSON.stringify({ token: token.trim(), new_password: newPassword }) });
}

function mapProject(row: any): DeveloperProject {
  return {
    projectId: String(row?.project_id || ''), name: String(row?.name || 'Untitled project'), framework: row?.framework ?? null,
    runtime: row?.runtime ?? null, language: row?.language ?? null, repositoryUrl: row?.repository_url ?? null,
    defaultBranch: row?.default_branch ?? null, createdAt: String(row?.created_at || ''), updatedAt: String(row?.updated_at || ''), lastEventAt: row?.last_event_at ?? null
  };
}

function mapEvent(row: any): DeveloperEvent {
  return {
    eventId: String(row?.event_id || ''), eventType: String(row?.event_type || 'event'), occurredAt: String(row?.occurred_at || ''),
    receivedAt: String(row?.received_at || ''), source: String(row?.source || 'cli'), metadata: row?.metadata && typeof row.metadata === 'object' ? row.metadata : {}
  };
}

export async function listDeveloperProjects(token: string): Promise<ApiResult<DeveloperProject[]>> {
  const result = await request<any[]>('/v1/developer/projects', { method: 'GET', headers: authHeaders(token) });
  if (!result.ok || !result.data) return result as ApiResult<DeveloperProject[]>;
  return { ...result, data: result.data.map(mapProject) };
}

export async function listDeveloperProjectEvents(token: string, projectId: string, limit = 50): Promise<ApiResult<DeveloperEvent[]>> {
  const safe = encodeURIComponent(projectId);
  const result = await request<any[]>(`/v1/developer/projects/${safe}/events?limit=${Math.max(1, Math.min(limit, 200))}`, { method: 'GET', headers: authHeaders(token) });
  if (!result.ok || !result.data) return result as ApiResult<DeveloperEvent[]>;
  return { ...result, data: result.data.map(mapEvent) };
}

export async function listDeveloperApiKeys(token: string): Promise<ApiResult<DeveloperApiKey[]>> {
  const result = await request<any[]>('/v1/developer/api-keys', { method: 'GET', headers: authHeaders(token) });
  if (!result.ok || !result.data) return result as ApiResult<DeveloperApiKey[]>;
  return { ...result, data: result.data.map(row => ({
    keyId: String(row?.key_id || ''), name: String(row?.name || 'Developer key'), keyPrefix: String(row?.key_prefix || ''),
    createdAt: String(row?.created_at || ''), lastUsedAt: row?.last_used_at ?? null, revokedAt: row?.revoked_at ?? null
  })) };
}
