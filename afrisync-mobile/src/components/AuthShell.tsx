import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { Brand } from './Brand';
import { Screen } from './Screen';
import { useTheme } from '../theme/theme';

export function AuthShell({ eyebrow, title, subtitle, children }: { eyebrow: string; title: string; subtitle: string; children: React.ReactNode }) {
  const { palette } = useTheme();
  return (
    <Screen padded={false} contentStyle={{ backgroundColor: palette.background }}>
      <View style={[styles.hero, { backgroundColor: palette.surfaceStrong }]}>
        <View style={styles.logo}><Brand auth /></View>
        <View style={styles.copyBlock}>
          <Text style={[styles.eyebrow, { color: palette.emerald }]}>{eyebrow.toUpperCase()}</Text>
          <Text style={[styles.title, { color: palette.white }]}>{title}</Text>
          <Text style={[styles.subtitle, { color: '#AEBBCD' }]}>{subtitle}</Text>
        </View>
      </View>
      <View style={[styles.body, { backgroundColor: palette.background }]}>{children}</View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  hero: { paddingHorizontal: 22, paddingTop: 28, paddingBottom: 32, borderBottomLeftRadius: 30, borderBottomRightRadius: 30 },
  logo: { alignItems: 'center', marginBottom: 24 },
  copyBlock: { width: '100%' },
  eyebrow: { fontSize: 11, fontWeight: '900', letterSpacing: 1.25 },
  title: { fontSize: 32, fontWeight: '900', letterSpacing: -1.0, lineHeight: 38, marginTop: 10 },
  subtitle: { fontSize: 14.5, lineHeight: 21, marginTop: 10, maxWidth: 520 },
  body: { paddingHorizontal: 18, paddingTop: 20, paddingBottom: 36, flexGrow: 1 }
});
