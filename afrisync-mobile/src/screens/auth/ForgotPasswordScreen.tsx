import React, { useState } from 'react';
import { Alert, Pressable, StyleSheet, Text, View } from 'react-native';
import { AppButton } from '../../components/AppButton';
import { AppInput } from '../../components/AppInput';
import { AuthShell } from '../../components/AuthShell';
import { Card } from '../../components/Screen';
import { useApp } from '../../context/AppContext';
import { requestPasswordReset, resetPassword } from '../../services/api';
import { useTheme } from '../../theme/theme';

export function ForgotPasswordScreen() {
  const { setScreen } = useApp();
  const { palette } = useTheme();
  const [identifier, setIdentifier] = useState('');
  const [token, setToken] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [loading, setLoading] = useState(false);

  async function requestReset() {
    if (!identifier.trim()) return Alert.alert('Reset password', 'Enter your email or username.');
    const result = await requestPasswordReset(identifier);
    const devToken = (result.data as any)?.development_reset_token;
    if (devToken) setToken(devToken);
    Alert.alert(result.ok ? 'Reset requested' : 'Unable to request reset', result.ok ? 'Check the account email for the reset token.' : result.error || 'Try again.');
  }

  async function submitReset() {
    if (!token.trim() || newPassword.length < 6) return Alert.alert('Reset password', 'Enter the reset token and a new password of at least 6 characters.');
    setLoading(true);
    const result = await resetPassword(token, newPassword);
    setLoading(false);
    if (!result.ok) return Alert.alert('Reset failed', result.error || 'Could not reset password.');
    Alert.alert('Password updated', 'You can now sign in with your new password.', [{ text: 'Sign in', onPress: () => setScreen('login') }]);
  }

  return (
    <AuthShell eyebrow="Account recovery" title="Reset your password securely." subtitle="Request a reset token from your registered account email, then choose a new password.">
      <Card>
        <View style={styles.form}>
          <AppInput label="Email or username" value={identifier} onChangeText={setIdentifier} autoCapitalize="none" />
          <AppButton title="Request reset token" variant="secondary" onPress={requestReset} />
          <AppInput label="Reset token" value={token} onChangeText={setToken} autoCapitalize="none" />
          <AppInput label="New password" value={newPassword} onChangeText={setNewPassword} secureTextEntry />
          <AppButton title="Update password" loading={loading} onPress={submitReset} />
        </View>
      </Card>
      <Pressable onPress={() => setScreen('login')} style={styles.back}><Text style={[styles.backText, { color: palette.textMuted }]}>Back to sign in</Text></Pressable>
    </AuthShell>
  );
}

const styles = StyleSheet.create({ form: { gap: 14 }, back: { alignItems: 'center', paddingVertical: 18 }, backText: { fontSize: 12.5, fontWeight: '800' } });
