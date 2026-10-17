import * as SecureStore from 'expo-secure-store';
import type { UserSession } from '../types';

const SESSION_KEYS = ['afrisync_mobile_session_v3', 'afrisync_mobile_session_v2', 'afrisync_mobile_session_v1'];

export async function saveSession(session: UserSession): Promise<void> {
  const serialized = JSON.stringify(session);
  await Promise.all(SESSION_KEYS.map(key => SecureStore.setItemAsync(key, serialized)));
}

export async function getSavedSession(): Promise<UserSession | null> {
  for (const key of SESSION_KEYS) {
    const raw = await SecureStore.getItemAsync(key);
    if (!raw) continue;
    try { return JSON.parse(raw) as UserSession; }
    catch { await SecureStore.deleteItemAsync(key); }
  }
  return null;
}

export async function clearSession(): Promise<void> {
  await Promise.all(SESSION_KEYS.map(key => SecureStore.deleteItemAsync(key)));
}
