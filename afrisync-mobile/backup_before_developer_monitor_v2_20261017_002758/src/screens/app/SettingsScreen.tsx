import React, { useEffect, useState } from 'react';
import { Alert, StyleSheet, Text, View } from 'react-native';
import { AppButton } from '../../components/AppButton';
import { AppInput } from '../../components/AppInput';
import { Card, Screen } from '../../components/Screen';
import { TopBar } from '../../components/TopBar';
import { explainMobileApiUrl, getApiBaseUrl, setApiBaseUrl } from '../../config/env';
import { useApp } from '../../context/AppContext';
import { healthCheck } from '../../services/api';
import { colors } from '../../theme/colors';

export function SettingsScreen() {
  const { setScreen } = useApp();
  const [apiUrl, setApiUrl] = useState('');

  useEffect(() => {
    getApiBaseUrl().then(setApiUrl);
  }, []);

  async function save() {
    await setApiBaseUrl(apiUrl);
    Alert.alert('Saved', 'API base URL updated.');
  }

  async function test() {
    await setApiBaseUrl(apiUrl);
    const result = await healthCheck();
    Alert.alert(result.ok ? 'Backend reachable' : 'Backend not reachable', result.ok ? JSON.stringify(result.data) : result.error || 'Check URL and network.');
  }

  return (
    <Screen>
      <TopBar title="Settings" onBack={() => setScreen('dashboard')} />
      <Card>
        <View style={styles.form}>
          <AppInput label="Backend API URL" value={apiUrl} onChangeText={setApiUrl} placeholder="http://192.168.1.10:8000" autoCapitalize="none" />
          <Text style={styles.help}>{explainMobileApiUrl()}</Text>
          <AppButton title="Save API URL" onPress={save} />
          <AppButton title="Test backend" variant="secondary" onPress={test} />
        </View>
      </Card>
    </Screen>
  );
}

const styles = StyleSheet.create({
  form: { gap: 14 },
  help: { color: colors.slate600, fontSize: 13, lineHeight: 20 }
});
