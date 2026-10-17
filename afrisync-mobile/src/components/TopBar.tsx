import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Brand } from './Brand';
import { useTheme } from '../theme/theme';

export function TopBar({ title, subtitle, onBack, right }: { title?: string; subtitle?: string; onBack?: () => void; right?: React.ReactNode }) {
  const { palette } = useTheme();
  return (
    <View style={styles.wrap}>
      <View style={styles.left}>
        {onBack ? (
          <Pressable onPress={onBack} style={[styles.back, { backgroundColor: palette.surface, borderColor: palette.border }]}>
            <Text style={[styles.backText, { color: palette.text }]}>‹</Text>
          </Pressable>
        ) : <Brand compact />}
        <View style={styles.titleWrap}>
          <Text style={[styles.title, { color: palette.text }]} numberOfLines={1}>{title || 'AfriSync'}</Text>
          {subtitle ? <Text style={[styles.subtitle, { color: palette.textSubtle }]} numberOfLines={1}>{subtitle}</Text> : null}
        </View>
      </View>
      {right}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 18, gap: 12 },
  left: { flexDirection: 'row', alignItems: 'center', gap: 10, flex: 1 },
  titleWrap: { flex: 1 },
  title: { fontSize: 20, fontWeight: '900', letterSpacing: -0.25 },
  subtitle: { marginTop: 2, fontSize: 11.5, fontWeight: '700' },
  back: { width: 42, height: 42, borderRadius: 13, alignItems: 'center', justifyContent: 'center', borderWidth: 1 },
  backText: { fontSize: 32, lineHeight: 32, marginTop: -2 }
});
