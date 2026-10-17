import React, { useCallback, useEffect, useState } from 'react';
import { Alert, Pressable, StyleSheet, Text, View } from 'react-native';
import { AppButton } from '../../components/AppButton';
import { AppInput } from '../../components/AppInput';
import { BottomNav } from '../../components/BottomNav';
import { Card, Screen } from '../../components/Screen';
import { StatusPill } from '../../components/StatusPill';
import { TopBar } from '../../components/TopBar';
import { getApiBaseUrl, isProductionApiLocked, mobileApiHelp, setApiBaseUrl, validateApiUrl } from '../../config/env';
import { useApp } from '../../context/AppContext';
import { listDeveloperApiKeys, testBackendUrl } from '../../services/api';
import { useTheme, type ThemeMode } from '../../theme/theme';
import type { DeveloperApiKey } from '../../types';
import { formatRelative } from '../../utils/format';

export function SettingsScreen() {
  const { session, signOut } = useApp();
  const { palette, mode, actualMode, setMode } = useTheme();
  const [url, setUrl] = useState('');
  const [keys, setKeys] = useState<DeveloperApiKey[]>([]);
  const [loading, setLoading] = useState(false);
  const productionLocked = isProductionApiLocked();

  const load = useCallback(async () => {
    setUrl(await getApiBaseUrl());
    if (session?.syncToken) {
      const result = await listDeveloperApiKeys(session.syncToken);
      if (result.ok && result.data) setKeys(result.data.filter(key => !key.revokedAt));
    }
  }, [session?.syncToken]);

  useEffect(() => { load(); }, [load]);

  async function testOrSave() {
    const validation = validateApiUrl(url);
    if (validation) return Alert.alert('Backend connection', validation);

    setLoading(true);
    const result = await testBackendUrl(url);
    setLoading(false);

    if (!result.ok) {
      return Alert.alert('Backend not reachable', result.error || 'Check FastAPI and your network.');
    }

    if (!productionLocked) {
      await setApiBaseUrl(url);
      return Alert.alert('Connected', 'Development backend connection verified and saved on this device.');
    }

    Alert.alert('Production connected', 'The production backend is reachable. The production URL is fixed by the app build.');
  }

  return (
    <Screen contentStyle={{ paddingTop: 32 }}>
      <TopBar title="Settings" subtitle="Account, appearance and developer integration" />

      <Text style={[styles.section, { color: palette.text }]}>Account</Text>
      <Card>
        <View style={styles.accountRow}>
          <View style={[styles.avatar, { backgroundColor: palette.primarySoft }]}>
            <Text style={[styles.avatarText, { color: palette.primary }]}>{(session?.username || 'A').slice(0, 1).toUpperCase()}</Text>
          </View>
          <View style={{ flex: 1 }}>
            <Text style={[styles.accountName, { color: palette.text }]}>{session?.fullName || session?.username || 'AfriSync developer'}</Text>
            <Text style={[styles.accountMeta, { color: palette.textMuted }]}>@{session?.username || 'developer'}{session?.email ? ` • ${session.email}` : ''}</Text>
          </View>
          <StatusPill label="VERIFIED" tone="good" />
        </View>
      </Card>

      <Text style={[styles.section, { color: palette.text }]}>Appearance</Text>
      <Card>
        <Text style={[styles.helper, { color: palette.textMuted }]}>Current appearance: {actualMode}. Choose a fixed theme or follow your phone.</Text>
        <View style={styles.themeRow}>
          {(['system', 'light', 'dark'] as ThemeMode[]).map(item => (
            <Pressable
              key={item}
              onPress={() => setMode(item)}
              style={[
                styles.themeOption,
                {
                  backgroundColor: mode === item ? palette.primarySoft : palette.surfaceAlt,
                  borderColor: mode === item ? palette.primary : palette.border
                }
              ]}
            >
              <Text style={[styles.themeText, { color: mode === item ? palette.primary : palette.textMuted }]}>{item.charAt(0).toUpperCase() + item.slice(1)}</Text>
            </Pressable>
          ))}
        </View>
      </Card>

      <Text style={[styles.section, { color: palette.text }]}>Developer integration</Text>
      <Card>
        <View style={styles.summaryRow}>
          <View>
            <Text style={[styles.summaryLabel, { color: palette.textMuted }]}>Active API keys</Text>
            <Text style={[styles.summaryValue, { color: palette.primary }]}>{keys.length}</Text>
          </View>
          <StatusPill label={keys.length ? 'CLI CONNECTED' : 'NO ACTIVE KEY'} tone={keys.length ? 'good' : 'neutral'} />
        </View>
        {keys.slice(0, 4).map(key => (
          <View key={key.keyId} style={[styles.keyRow, { borderTopColor: palette.border }]}>
            <View style={{ flex: 1 }}>
              <Text style={[styles.keyName, { color: palette.text }]}>{key.name}</Text>
              <Text style={[styles.keyPrefix, { color: palette.textSubtle }]}>{key.keyPrefix}••••</Text>
            </View>
            <Text style={[styles.keyUsed, { color: palette.textSubtle }]}>Last used{`\n`}{formatRelative(key.lastUsedAt)}</Text>
          </View>
        ))}
        <Text style={[styles.helper, { color: palette.textMuted }]}>Secret keys stay on your developer machine. AfriSync Mobile only shows safe metadata.</Text>
      </Card>

      <Text style={[styles.section, { color: palette.text }]}>Backend connection</Text>
      <Card>
        <View style={styles.connectionHeader}>
          <Text style={[styles.connectionMode, { color: palette.text }]}>{productionLocked ? 'Production endpoint' : 'Development endpoint'}</Text>
          <StatusPill label={productionLocked ? 'BUILD LOCKED' : 'EDITABLE'} tone={productionLocked ? 'good' : 'warn'} />
        </View>
        <Text style={[styles.helper, { color: palette.textMuted, marginBottom: 12 }]}>{mobileApiHelp}</Text>
        <View style={styles.form}>
          <AppInput
            label="Backend API URL"
            value={url}
            onChangeText={setUrl}
            autoCapitalize="none"
            autoCorrect={false}
            editable={!productionLocked}
          />
          <AppButton
            title={productionLocked ? 'Test production connection' : 'Test and save development connection'}
            loading={loading}
            onPress={testOrSave}
          />
        </View>
      </Card>

      <Text style={[styles.section, { color: palette.text }]}>Security</Text>
      <Card>
        <Text style={[styles.helper, { color: palette.textMuted }]}>Signing out removes the saved mobile session from this device. Developer CLI credentials are managed separately on your computer.</Text>
        <View style={{ marginTop: 14 }}><AppButton title="Sign out" variant="danger" onPress={signOut} /></View>
      </Card>

      <Text style={[styles.version, { color: palette.textSubtle }]}>AfriSync Mobile • Developer Monitor v1</Text>
      <BottomNav active="settings" />
    </Screen>
  );
}

const styles = StyleSheet.create({
  section: { fontSize: 18, fontWeight: '900', marginTop: 20, marginBottom: 9 },
  accountRow: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  avatar: { width: 44, height: 44, borderRadius: 14, alignItems: 'center', justifyContent: 'center' },
  avatarText: { fontSize: 18, fontWeight: '900' },
  accountName: { fontSize: 16, fontWeight: '900' },
  accountMeta: { fontSize: 11.5, marginTop: 4 },
  helper: { fontSize: 12, lineHeight: 18 },
  themeRow: { flexDirection: 'row', gap: 8, marginTop: 14 },
  themeOption: { flex: 1, borderWidth: 1, borderRadius: 12, alignItems: 'center', paddingVertical: 11 },
  themeText: { fontSize: 12, fontWeight: '900' },
  summaryRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  summaryLabel: { fontSize: 12, fontWeight: '800' },
  summaryValue: { fontSize: 28, fontWeight: '900', marginTop: 3 },
  keyRow: { flexDirection: 'row', alignItems: 'center', borderTopWidth: 1, paddingTop: 12, marginTop: 12 },
  keyName: { fontSize: 13.5, fontWeight: '900' },
  keyPrefix: { fontSize: 11, marginTop: 3 },
  keyUsed: { fontSize: 9.5, textAlign: 'right', lineHeight: 14 },
  connectionHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 10, marginBottom: 6 },
  connectionMode: { fontSize: 14, fontWeight: '900' },
  form: { gap: 14 },
  version: { textAlign: 'center', fontSize: 10.5, marginTop: 22, fontWeight: '700' }
});
