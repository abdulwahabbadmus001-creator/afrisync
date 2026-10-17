import React, { useState } from 'react';
import { Alert, StyleSheet, Text, View } from 'react-native';
import { AppButton } from '../../components/AppButton';
import { AppInput } from '../../components/AppInput';
import { Brand } from '../../components/Brand';
import { Card, Screen } from '../../components/Screen';
import { useApp } from '../../context/AppContext';
import { loginWithPassword } from '../../services/api';
import { colors } from '../../theme/colors';

export function LoginScreen() {
  const { signIn, setScreen } = useApp();
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);

  async function submit() {
    if (!identifier || !password) {
      Alert.alert('Missing details', 'Enter your email/username and password.');
      return;
    }
    setLoading(true);
    const result = await loginWithPassword(identifier, password);
    setLoading(false);
    if (!result.ok || !result.data) {
      Alert.alert('Login failed', result.error || 'Check your details and try again.');
      return;
    }
    await signIn(result.data);
  }

  return (
    <Screen>
      <View style={styles.hero}>
        <Brand />
        <Text style={styles.heading}>Offline-first project sync for African builders.</Text>
        <Text style={styles.subheading}>Sign in to continue building, even when the network is unreliable.</Text>
      </View>

      <Card>
        <Text style={styles.cardTitle}>Welcome back</Text>
        <View style={styles.form}>
          <AppInput label="Email or username" value={identifier} onChangeText={setIdentifier} placeholder="you@example.com" keyboardType="email-address" />
          <AppInput label="Password" value={password} onChangeText={setPassword} placeholder="••••••••" secureTextEntry />
          <AppButton title="Sign in" loading={loading} onPress={submit} />
          <AppButton title="Create account" variant="secondary" onPress={() => setScreen('register')} />
          <AppButton title="Forgot password?" variant="ghost" onPress={() => setScreen('forgot-password')} />
        </View>
      </Card>

      <Text style={styles.note}>Google sign-in will be added after the mobile backend callback is stabilized.</Text>
    </Screen>
  );
}

const styles = StyleSheet.create({
  hero: { gap: 14, marginBottom: 24 },
  heading: { color: colors.slate950, fontSize: 32, fontWeight: '900', letterSpacing: -1.1, lineHeight: 38, marginTop: 22 },
  subheading: { color: colors.slate600, fontSize: 15, lineHeight: 22 },
  cardTitle: { color: colors.slate950, fontSize: 22, fontWeight: '900', marginBottom: 16 },
  form: { gap: 14 },
  note: { textAlign: 'center', color: colors.slate500, marginTop: 18, fontSize: 12, lineHeight: 18 }
});
