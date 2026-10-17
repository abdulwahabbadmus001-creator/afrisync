export type RootScreen =
  | 'login'
  | 'register'
  | 'verify-email'
  | 'forgot-password'
  | 'dashboard'
  | 'projects'
  | 'create-project'
  | 'project-details'
  | 'sync-center'
  | 'notifications'
  | 'settings';

export type SyncStatus = 'SYNCED' | 'PENDING' | 'CONFLICT' | 'ERROR';

export type UserSession = {
  userId: string;
  username: string;
  email?: string;
  fullName?: string;
  syncToken: string;
};

export type Project = {
  projectUuid: string;
  name: string;
  location: string;
  progress: number;
  description?: string;
  syncStatus: SyncStatus;
  isDeleted: number;
  version: number;
  updatedAt: string;
  createdAt: string;
};

export type Note = {
  noteUuid: string;
  projectUuid: string;
  content: string;
  syncStatus: SyncStatus;
  isDeleted: number;
  updatedAt: string;
  createdAt: string;
};

export type NotificationItem = {
  id: string;
  title: string;
  body: string;
  type: 'success' | 'warning' | 'error' | 'info';
  isRead: number;
  createdAt: string;
};

export type ApiResult<T> = {
  ok: boolean;
  data?: T;
  error?: string;
};

export type AuthMode = 'signin' | 'signup' | 'verify' | 'forgot';
