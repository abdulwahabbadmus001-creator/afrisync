import React, { useState } from 'react';
import { Alert, Pressable, StyleSheet, Text, View } from 'react-native';
import { AppButton } from '../../components/AppButton';
import { AppInput } from '../../components/AppInput';
import { AuthShell } from '../../components/AuthShell';
import { Card } from '../../components/Screen';
import { useApp } from '../../context/AppContext';
import { resendVerification, verifyEmail } from '../../services/api';
import { useTheme } from '../../theme/theme';

export function VerifyEmailScreen() {
  const { verificationIdentifier, setScreen, signIn } = useApp();
  const { palette } = useTheme();
  const [identifier, setIdentifier] = useState(verificationIdentifier);
  const [code, setCode] = useState('');
  const [loading, setLoading] = useState(false);

  async function submit() {
    if (!identifier.trim() || !/^\d{4}$/.test(code.trim())) return Alert.alert('Verification', 'Enter your email or username and the 4-digit code.');
    setLoading(true);
    const result = await verifyEmail(identifier, code);
    setLoading(false);
    if (!result.ok || !result.data) return Alert.alert('Verification failed', result.error || 'The code is invalid or expired.');
    await signIn(result.data);
  }

  async function resend() {
    if (!identifier.trim()) return Alert.alert('Verification', 'Enter your email or username first.');
    const result = await resendVerification(identifier);
    Alert.alert(result.ok ? 'Code sent' : 'Unable to resend', result.ok ? 'Check your inbox and spam folder.' : result.error || 'Try again.');
  }

  return (
    <AuthShell eyebrow="Email verification" title="Confirm it’s you." subtitle="Enter the 4-digit code sent by AfriSync. Once verified, your account opens directly into the developer overview.">
      <Card>
        <View style={styles.form}>
          <AppInput label="Email or username" value={identifier} onChangeText={setIdentifier} autoCapitalize="none" />
          <AppInput label="4-digit code" value={code} onChangeText={setCode} keyboardType="number-pad" maxLength={4} placeholder="0000" />
          <AppButton title="Verify and continue" loading={loading} onPress={submit} />
          <AppButton title="Resend code" variant="secondary" onPress={resend} />
        </View>
      </Card>
      <Pressable onPress={() => setScreen('login')} style={styles.back}><Text style={[styles.backText, { color: palette.textMuted }]}>Back to sign in</Text></Pressable>
    </AuthShell>
  );
}

const styles = StyleSheet.create({ form: { gap: 14 }, back: { alignItems: 'center', paddingVertical: 18 }, backText: { fontSize: 12.5, fontWeight: '800' } });
