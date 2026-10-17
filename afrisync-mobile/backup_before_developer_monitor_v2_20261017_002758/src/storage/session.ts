import * as SecureStore from 'expo-secure-store';
import type { UserSession } from '../types';

const SESSION_KEY = 'afrisync_mobile_session_v1';

export async function saveSession(session: UserSession): Promise<void> {
  await SecureStore.setItemAsync(SESSION_KEY, JSON.stringify(session));
}

export async function getSavedSession(): Promise<UserSession | null> {
  const raw = await SecureStore.getItemAsync(SESSION_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as UserSession;
  } catch {
    await clearSession();
    return null;
  }
}

export async function clearSession(): Promise<void> {
  await SecureStore.deleteItemAsync(SESSION_KEY);
}
