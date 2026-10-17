import * as SecureStore from 'expo-secure-store';

export const DEFAULT_API_BASE_URL = 'http://127.0.0.1:8000';
export const API_BASE_URL_KEY = 'afrisync_api_base_url';

export async function getApiBaseUrl(): Promise<string> {
  const saved = await SecureStore.getItemAsync(API_BASE_URL_KEY);
  return saved || DEFAULT_API_BASE_URL;
}

export async function setApiBaseUrl(url: string): Promise<void> {
  const normalized = url.trim().replace(/\/$/, '');
  await SecureStore.setItemAsync(API_BASE_URL_KEY, normalized);
}

export function explainMobileApiUrl(): string {
  return 'For phone testing, use your laptop IP, for example http://192.168.1.10:8000, not 127.0.0.1.';
}
