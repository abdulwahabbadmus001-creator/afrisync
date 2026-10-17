import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { useTheme } from '../theme/theme';

export function StatusPill({ label, tone = 'neutral' }: { label: string; tone?: 'good' | 'warn' | 'bad' | 'info' | 'neutral' }) {
  const { palette } = useTheme();
  const color = tone === 'good' ? palette.emerald : tone === 'warn' ? palette.amber : tone === 'bad' ? palette.red : tone === 'info' ? palette.primary : palette.textMuted;
  const backgroundColor = tone === 'good' ? palette.emeraldSoft : tone === 'warn' ? palette.amberSoft : tone === 'bad' ? palette.redSoft : tone === 'info' ? palette.primarySoft : palette.surfaceAlt;
  return <View style={[styles.pill, { backgroundColor }]}><View style={[styles.dot, { backgroundColor: color }]} /><Text style={[styles.text, { color }]}>{label}</Text></View>;
}

const styles = StyleSheet.create({
  pill: { flexDirection: 'row', alignItems: 'center', alignSelf: 'flex-start', borderRadius: 999, paddingHorizontal: 9, paddingVertical: 6 },
  dot: { width: 6, height: 6, borderRadius: 999, marginRight: 6 },
  text: { fontSize: 10.5, fontWeight: '900', letterSpacing: 0.25 }
});
