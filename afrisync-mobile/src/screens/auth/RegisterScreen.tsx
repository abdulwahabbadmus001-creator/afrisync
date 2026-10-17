import React, { useState } from 'react';
import { Alert, Pressable, StyleSheet, Text, View } from 'react-native';
import { AppButton } from '../../components/AppButton';
import { AppInput } from '../../components/AppInput';
import { AuthShell } from '../../components/AuthShell';
import { Card } from '../../components/Screen';
import { useApp } from '../../context/AppContext';
import { registerAccount } from '../../services/api';
import { useTheme } from '../../theme/theme';

export function RegisterScreen() {
  const { setScreen, setVerificationIdentifier, signIn } = useApp();
  const { palette } = useTheme();
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);

  async function submit() {
    if (!fullName.trim() || !email.trim() || !username.trim() || !password) return Alert.alert('Create account', 'Complete all required fields.');
    if (password.length < 6) return Alert.alert('Password', 'Use at least 6 characters.');
    setLoading(true);
    const result = await registerAccount({ fullName, email, username, password });
    setLoading(false);
    if (!result.ok || !result.data) return Alert.alert('Unable to create account', result.error || 'Try again.');
    if (result.data.session) return signIn(result.data.session);
    setVerificationIdentifier(result.data.identifier);
    setScreen('verify-email');
  }

  return (
    <AuthShell eyebrow="Create account" title="One account for your development activity." subtitle="Create your AfriSync identity once. Your CLI and SDK will register projects and send activity automatically.">
      <Card>
        <Text style={[styles.cardTitle, { color: palette.text }]}>Developer account</Text>
        <Text style={[styles.cardCopy, { color: palette.textMuted }]}>Use an email you can access for the 4-digit verification code.</Text>
        <View style={styles.form}>
          <AppInput label="Full name" value={fullName} onChangeText={setFullName} autoCapitalize="words" placeholder="Your full name" />
          <AppInput label="Email" value={email} onChangeText={setEmail} autoCapitalize="none" keyboardType="email-address" placeholder="you@gmail.com" />
          <AppInput label="Username" value={username} onChangeText={setUsername} autoCapitalize="none" autoCorrect={false} placeholder="your_username" />
          <AppInput label="Password" value={password} onChangeText={setPassword} secureTextEntry placeholder="At least 6 characters" helper="Use a password you do not reuse elsewhere." />
          <AppButton title="Create account" loading={loading} onPress={submit} />
        </View>
      </Card>
      <View style={styles.footerRow}>
        <Text style={[styles.footerText, { color: palette.textMuted }]}>Already have an account?</Text>
        <Pressable onPress={() => setScreen('login')}><Text style={[styles.footerLink, { color: palette.primary }]}>Sign in</Text></Pressable>
      </View>
    </AuthShell>
  );
}

const styles = StyleSheet.create({
  cardTitle: { fontSize: 22, fontWeight: '900', letterSpacing: -0.35 },
  cardCopy: { fontSize: 13.5, lineHeight: 19, marginTop: 5, marginBottom: 18 },
  form: { gap: 14 },
  footerRow: { flexDirection: 'row', justifyContent: 'center', gap: 6, marginTop: 18 },
  footerText: { fontSize: 13.5 },
  footerLink: { fontSize: 13.5, fontWeight: '900' }
});
