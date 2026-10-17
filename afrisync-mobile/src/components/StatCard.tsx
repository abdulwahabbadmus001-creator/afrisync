import React from 'react';
import { Pressable, StyleSheet, Text } from 'react-native';
import { colors } from '../theme/colors';

export function StatCard({ label, value, accent, onPress }: { label: string; value: string | number; accent?: string; onPress?: () => void }) {
  return (
    <Pressable onPress={onPress} style={({ pressed }) => [styles.card, pressed && styles.pressed]}>
      <Text style={[styles.value, { color: accent || colors.blue }]}>{value}</Text>
      <Text style={styles.label}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    width: '48%',
    backgroundColor: colors.white,
    borderRadius: 20,
    padding: 16,
    borderWidth: 1,
    borderColor: colors.slate200
  },
  pressed: { opacity: 0.82 },
  value: { fontSize: 30, fontWeight: '900' },
  label: { marginTop: 4, color: colors.slate600, fontSize: 13, fontWeight: '800' }
});
