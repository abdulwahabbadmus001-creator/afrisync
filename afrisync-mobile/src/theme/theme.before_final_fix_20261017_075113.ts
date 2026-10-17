import { colors } from './colors';

export const spacing = {
  xs: 6,
  sm: 10,
  md: 16,
  lg: 24,
  xl: 32
};

export const radius = {
  sm: 10,
  md: 16,
  lg: 24,
  pill: 999
};

export const lightTheme = {
  mode: 'light' as const,
  background: colors.slate50,
  surface: colors.white,
  surfaceAlt: colors.slate100,
  text: colors.slate950,
  muted: colors.slate500,
  border: colors.slate200,
  primary: colors.blue,
  accent: colors.emerald,
  warning: colors.amber,
  danger: colors.red,
  cardShadow: '#CBD5E1'
};

export const darkTheme = {
  mode: 'dark' as const,
  background: colors.slate950,
  surface: '#0B1628',
  surfaceAlt: '#111D31',
  text: colors.white,
  muted: '#9AA8BC',
  border: '#22304A',
  primary: '#60A5FA',
  accent: '#34D399',
  warning: '#FBBF24',
  danger: '#F87171',
  cardShadow: '#020617'
};

export type AppTheme = typeof lightTheme;
