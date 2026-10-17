import React, { useEffect, useState } from 'react';
import { Alert, Pressable, StyleSheet, Text, View } from 'react-native';
import { AppButton } from '../../components/AppButton';
import { AppInput } from '../../components/AppInput';
import { AuthShell } from '../../components/AuthShell';
import { Card } from '../../components/Screen';
import { getApiBaseUrl, mobileApiHelp, setApiBaseUrl, validateApiUrl } from '../../config/env';
import { useApp } from '../../context/AppContext';
import { testBackendUrl } from '../../services/api';
import { useTheme } from '../../theme/theme';

export function BackendSetupScreen() {
  const { session, setScreen } = useApp();
  const { palette } = useTheme();
  const [url, setUrl] = useState('');
  const [loading, setLoading] = useState(false);
  useEffect(() => { getApiBaseUrl().then(setUrl); }, []);

  async function connect() {
    const validation = validateApiUrl(url);
    if (validation) return Alert.alert('Backend connection', validation);
    setLoading(true);
    const result = await testBackendUrl(url);
    setLoading(false);
    if (!result.ok) return Alert.alert('Backend not reachable', `${result.error || 'Connection failed'}\n\n${mobileApiHelp}`);
    await setApiBaseUrl(url);
    setScreen(session ? 'dashboard' : 'login');
  }

  return (
    <AuthShell eyebrow="Connection" title="Connect AfriSync Mobile to your backend." subtitle="For local testing, the phone and laptop must be on the same network. Use the laptop’s Wi-Fi IPv4 address.">
      <Card>
        <View style={styles.form}>
          <AppInput label="Backend API URL" value={url} onChangeText={setUrl} autoCapitalize="none" autoCorrect={false} placeholder="http://10.52.125.196:8000" helper={mobileApiHelp} />
          <AppButton title="Test and save connection" loading={loading} onPress={connect} />
        </View>
      </Card>
      {url ? <Pressable onPress={() => setScreen(session ? 'dashboard' : 'login')} style={styles.back}><Text style={[styles.backText, { color: palette.textMuted }]}>Return without changing</Text></Pressable> : null}
    </AuthShell>
  );
}

const styles = StyleSheet.create({ form: { gap: 14 }, back: { alignItems: 'center', paddingVertical: 18 }, backText: { fontSize: 12.5, fontWeight: '800' } });
