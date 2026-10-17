declare const process: {
  env: {
    EXPO_PUBLIC_AFRISYNC_API_URL?: string;
  };
};

import * as SecureStore from 'expo-secure-store';

const API_BASE_URL_KEYS = [
  'afrisync_api_base_url_v4',
  'afrisync_api_base_url_v3',
  'afrisync_api_base_url_v2',
  'afrisync_api_base_url',
];

const PRODUCTION_API_URL =
  'https://afrisync-remote-api.onrender.com';

export function normalizeApiUrl(url: string): string {
  return url.trim().replace(/\/+$/, '');
}

const BUILD_API_URL = normalizeApiUrl(
  process.env.EXPO_PUBLIC_AFRISYNC_API_URL ||
    PRODUCTION_API_URL
);

export function getBuildApiUrl(): string {
  return BUILD_API_URL;
}

export function isProductionApiLocked(): boolean {
  return !__DEV__ && Boolean(BUILD_API_URL);
}

export async function getApiBaseUrl(): Promise<string> {
  if (!__DEV__) {
    return BUILD_API_URL || PRODUCTION_API_URL;
  }

  for (const key of API_BASE_URL_KEYS) {
    const value = await SecureStore.getItemAsync(key);

    if (value) {
      return normalizeApiUrl(value);
    }
  }

  return BUILD_API_URL || PRODUCTION_API_URL;
}

export async function setApiBaseUrl(
  url: string
): Promise<void> {
  if (isProductionApiLocked()) {
    return;
  }

  const normalized = normalizeApiUrl(url);

  if (!normalized) {
    await Promise.all(
      API_BASE_URL_KEYS.map((key) =>
        SecureStore.deleteItemAsync(key)
      )
    );

    return;
  }

  await Promise.all(
    API_BASE_URL_KEYS.map((key) =>
      SecureStore.setItemAsync(key, normalized)
    )
  );
}

export function validateApiUrl(
  url: string
): string | null {
  const normalized = normalizeApiUrl(url);

  if (!normalized) {
    return 'Enter your AfriSync backend URL.';
  }

  if (!/^https?:\/\//i.test(normalized)) {
    return 'URL must begin with http:// or https://';
  }

  if (/127\.0\.0\.1|localhost/i.test(normalized)) {
    return 'On a physical phone, use your laptop IPv4 address instead of localhost.';
  }

  if (!__DEV__ && !/^https:\/\//i.test(normalized)) {
    return 'Production builds require an HTTPS backend URL.';
  }

  return null;
}

export const mobileApiHelp = __DEV__
  ? 'Development only: use your laptop Wi-Fi IPv4 address, for example http://192.168.1.10:8000.'
  : 'Production connection: https://afrisync-remote-api.onrender.com';
