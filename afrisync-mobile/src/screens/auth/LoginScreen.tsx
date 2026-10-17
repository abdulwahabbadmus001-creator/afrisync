import React, { useEffect, useState } from 'react';
import { Alert, Pressable, StyleSheet, Text, View } from 'react-native';
import { AppButton } from '../../components/AppButton';
import { AppInput } from '../../components/AppInput';
import { AuthShell } from '../../components/AuthShell';
import { Card } from '../../components/Screen';
import { getApiBaseUrl } from '../../config/env';
import { useApp } from '../../context/AppContext';
import { loginWithPassword } from '../../services/api';
import { useTheme } from '../../theme/theme';

export function LoginScreen() {
  const { signIn, setScreen, setVerificationIdentifier } = useApp();
  const { palette } = useTheme();
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [apiUrl, setApiUrl] = useState('');
  useEffect(() => { getApiBaseUrl().then(setApiUrl); }, []);

  async function submit() {
    if (!identifier.trim() || !password) return Alert.alert('Sign in', 'Enter your email or username and password.');
    setLoading(true);
    const result = await loginWithPassword(identifier, password);
    setLoading(false);
    if (!result.ok || !result.data) {
      if (result.status === 403 && /verification/i.test(result.error || '')) {
        setVerificationIdentifier(identifier.trim());
        return Alert.alert('Verification required', 'Verify your email before signing in.', [{ text: 'Verify email', onPress: () => setScreen('verify-email') }]);
      }
      return Alert.alert('Unable to sign in', result.error || 'Check your credentials and backend connection.');
    }
    await signIn(result.data);
  }

  return (
    <AuthShell eyebrow="Developer platform" title="Your work. In sync." subtitle="Monitor projects registered from your codebase, development sessions and sync health from one place.">
      <Card>
        <Text style={[styles.cardTitle, { color: palette.text }]}>Sign in</Text>
        <Text style={[styles.cardCopy, { color: palette.textMuted }]}>Use the account connected to your AfriSync CLI.</Text>
        <View style={styles.form}>
          <AppInput label="Email or username" value={identifier} onChangeText={setIdentifier} placeholder="you@example.com" autoCapitalize="none" autoCorrect={false} />
          <AppInput label="Password" value={password} onChangeText={setPassword} placeholder="Enter your password" secureTextEntry />
          <View style={styles.linkRow}>
            <Text style={[styles.backendText, { color: palette.textSubtle }]} numberOfLines={1}>Backend {apiUrl ? 'connected' : 'not configured'}</Text>
            <Pressable onPress={() => setScreen('forgot-password')}><Text style={[styles.link, { color: palette.primary }]}>Forgot password?</Text></Pressable>
          </View>
          <AppButton title="Sign in" loading={loading} onPress={submit} />
        </View>
      </Card>
      <View style={styles.footerRow}>
        <Text style={[styles.footerText, { color: palette.textMuted }]}>New to AfriSync?</Text>
        <Pressable onPress={() => setScreen('register')}><Text style={[styles.footerLink, { color: palette.primary }]}>Create account</Text></Pressable>
      </View>
      <Pressable onPress={() => setScreen('backend-setup')} style={styles.connectionLink}>
        <Text style={[styles.connectionText, { color: palette.textSubtle }]}>Change backend connection</Text>
      </Pressable>
    </AuthShell>
  );
}

const styles = StyleSheet.create({
  cardTitle: { fontSize: 22, fontWeight: '900', letterSpacing: -0.35 },
  cardCopy: { fontSize: 13.5, lineHeight: 19, marginTop: 5, marginBottom: 18 },
  form: { gap: 14 },
  linkRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: 12 },
  backendText: { fontSize: 11.5, flex: 1 },
  link: { fontSize: 12.5, fontWeight: '800' },
  footerRow: { flexDirection: 'row', justifyContent: 'center', gap: 6, marginTop: 18 },
  footerText: { fontSize: 13.5 },
  footerLink: { fontSize: 13.5, fontWeight: '900' },
  connectionLink: { alignItems: 'center', marginTop: 16, paddingVertical: 8 },
  connectionText: { fontSize: 11.5, fontWeight: '700' }
});
