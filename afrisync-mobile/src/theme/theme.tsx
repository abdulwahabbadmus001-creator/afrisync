import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';
import { useColorScheme } from 'react-native';
import * as SecureStore from 'expo-secure-store';

export type ThemeMode = 'system' | 'light' | 'dark';

export type Palette = {
  background: string;
  surface: string;
  surfaceAlt: string;
  surfaceStrong: string;
  border: string;
  borderStrong: string;
  text: string;
  textMuted: string;
  textSubtle: string;
  primary: string;
  primaryPressed: string;
  primarySoft: string;
  emerald: string;
  emeraldSoft: string;
  amber: string;
  amberSoft: string;
  red: string;
  redSoft: string;
  white: string;
  black: string;
  shadow: string;
  input: string;
  overlay: string;
};

const light: Palette = {
  background: '#F4F7FB',
  surface: '#FFFFFF',
  surfaceAlt: '#EEF3F9',
  surfaceStrong: '#08111F',
  border: '#DFE7F1',
  borderStrong: '#C9D5E3',
  text: '#0B1320',
  textMuted: '#526174',
  textSubtle: '#7A899A',
  primary: '#1976F3',
  primaryPressed: '#0E5FD0',
  primarySoft: '#E7F0FF',
  emerald: '#159A7D',
  emeraldSoft: '#E0F7F1',
  amber: '#D89013',
  amberSoft: '#FFF1D5',
  red: '#D94C59',
  redSoft: '#FFE7EA',
  white: '#FFFFFF',
  black: '#000000',
  shadow: '#08111F',
  input: '#F8FAFD',
  overlay: 'rgba(8,17,31,0.07)'
};

const dark: Palette = {
  background: '#070B12',
  surface: '#0D1420',
  surfaceAlt: '#111C2B',
  surfaceStrong: '#050A12',
  border: '#1C2A3B',
  borderStrong: '#2A3B50',
  text: '#F5F8FC',
  textMuted: '#A4B1C0',
  textSubtle: '#78899C',
  primary: '#4A91FF',
  primaryPressed: '#6AA5FF',
  primarySoft: '#102A4C',
  emerald: '#31CFA6',
  emeraldSoft: '#0D3029',
  amber: '#F2B544',
  amberSoft: '#3B2A0E',
  red: '#FF7580',
  redSoft: '#3C171D',
  white: '#FFFFFF',
  black: '#000000',
  shadow: '#000000',
  input: '#0A111B',
  overlay: 'rgba(255,255,255,0.06)'
};

const THEME_KEY = 'afrisync_theme_mode_v1';

type ThemeContextValue = {
  mode: ThemeMode;
  actualMode: 'light' | 'dark';
  palette: Palette;
  setMode: (mode: ThemeMode) => Promise<void>;
};

const ThemeContext = createContext<ThemeContextValue | undefined>(undefined);

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const system = useColorScheme();
  const [mode, setModeState] = useState<ThemeMode>('system');

  useEffect(() => {
    SecureStore.getItemAsync(THEME_KEY).then(saved => {
      if (saved === 'system' || saved === 'light' || saved === 'dark') setModeState(saved);
    });
  }, []);

  const actualMode: 'light' | 'dark' = mode === 'system' ? (system === 'dark' ? 'dark' : 'light') : mode;
  const palette = actualMode === 'dark' ? dark : light;

  const value = useMemo<ThemeContextValue>(() => ({
    mode,
    actualMode,
    palette,
    async setMode(next) {
      setModeState(next);
      await SecureStore.setItemAsync(THEME_KEY, next);
    }
  }), [mode, actualMode, palette]);

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const value = useContext(ThemeContext);
  if (!value) throw new Error('useTheme must be used inside ThemeProvider');
  return value;
}
