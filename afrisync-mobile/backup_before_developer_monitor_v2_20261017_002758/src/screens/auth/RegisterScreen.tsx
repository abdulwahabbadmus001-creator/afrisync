import React, { useState } from 'react';
import { Alert, StyleSheet, Text, View } from 'react-native';
import { AppButton } from '../../components/AppButton';
import { AppInput } from '../../components/AppInput';
import { Card, Screen } from '../../components/Screen';
import { TopBar } from '../../components/TopBar';
import { useApp } from '../../context/AppContext';
import { registerAccount } from '../../services/api';
import { colors } from '../../theme/colors';

export function RegisterScreen() {
  const { setScreen, setVerificationEmail } = useApp();
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);

  async function submit() {
    if (!fullName || !email || !username || !password) {
      Alert.alert('Missing details', 'Fill all fields to create an account.');
      return;
    }
    setLoading(true);
    const result = await registerAccount({ fullName, email, username, password });
    setLoading(false);
    if (!result.ok) {
      Alert.alert('Registration failed', result.error || 'Unable to create account.');
      return;
    }
    setVerificationEmail(email);
    setScreen('verify-email');
  }

  return (
    <Screen>
      <TopBar title="Create account" onBack={() => setScreen('login')} />
      <Text style={styles.copy}>Create an AfriSync account and verify your email before syncing projects across devices.</Text>
      <Card>
        <View style={styles.form}>
          <AppInput label="Full name" value={fullName} onChangeText={setFullName} placeholder="Wahab Opeyemi Badmus" autoCapitalize="words" />
          <AppInput label="Email" value={email} onChangeText={setEmail} placeholder="you@gmail.com" keyboardType="email-address" />
          <AppInput label="Username" value={username} onChangeText={setUsername} placeholder="elprofessor_001" />
          <AppInput label="Password" value={password} onChangeText={setPassword} placeholder="Create a strong password" secureTextEntry />
          <AppButton title="Create account" loading={loading} onPress={submit} />
        </View>
      </Card>
    </Screen>
  );
}

const styles = StyleSheet.create({
  copy: { color: colors.slate600, fontSize: 15, lineHeight: 22, marginBottom: 18 },
  form: { gap: 14 }
});
