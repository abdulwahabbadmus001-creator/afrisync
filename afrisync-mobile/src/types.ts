export type RootScreen =
  | 'backend-setup'
  | 'login'
  | 'register'
  | 'verify-email'
  | 'forgot-password'
  | 'dashboard'
  | 'projects'
  | 'project-details'
  | 'sync-center'
  | 'notifications'
  | 'settings';

export type UserSession = {
  userId: string;
  username: string;
  email?: string;
  fullName?: string;
  syncToken: string;
  syncTokenExpiresAt?: string;
};

export type DeveloperProject = {
  projectId: string;
  name: string;
  framework?: string | null;
  runtime?: string | null;
  language?: string | null;
  repositoryUrl?: string | null;
  defaultBranch?: string | null;
  createdAt: string;
  updatedAt: string;
  lastEventAt?: string | null;
};

export type DeveloperEvent = {
  eventId: string;
  eventType: string;
  occurredAt: string;
  receivedAt: string;
  source: string;
  metadata: Record<string, unknown>;
};

export type DeveloperApiKey = {
  keyId: string;
  name: string;
  keyPrefix: string;
  createdAt: string;
  lastUsedAt?: string | null;
  revokedAt?: string | null;
};

export type ApiResult<T> = {
  ok: boolean;
  data?: T;
  error?: string;
  status?: number;
  detail?: unknown;
};
