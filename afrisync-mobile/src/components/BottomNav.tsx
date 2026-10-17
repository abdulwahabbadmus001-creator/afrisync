import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { useApp } from '../context/AppContext';
import { useTheme } from '../theme/theme';
import type { RootScreen } from '../types';

const items: Array<{ label: string; screen: RootScreen }> = [
  { label: 'Overview', screen: 'dashboard' },
  { label: 'Projects', screen: 'projects' },
  { label: 'Sync', screen: 'sync-center' },
  { label: 'Settings', screen: 'settings' }
];

export function BottomNav({ active }: { active: RootScreen }) {
  const { setScreen } = useApp();
  const { palette } = useTheme();
  return (
    <View style={[styles.wrap, { backgroundColor: palette.surface, borderColor: palette.border }]}>
      {items.map(item => {
        const isActive = item.screen === active;
        return (
          <Pressable key={item.screen} onPress={() => setScreen(item.screen)} style={styles.item}>
            <View style={[styles.indicator, { backgroundColor: isActive ? palette.primary : 'transparent' }]} />
            <Text style={[styles.label, { color: isActive ? palette.primary : palette.textSubtle }]}>{item.label}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { flexDirection: 'row', borderWidth: 1, borderRadius: 18, paddingVertical: 5, marginTop: 22 },
  item: { flex: 1, alignItems: 'center', paddingVertical: 8 },
  indicator: { width: 22, height: 3, borderRadius: 999, marginBottom: 6 },
  label: { fontSize: 11.5, fontWeight: '800' }
});
