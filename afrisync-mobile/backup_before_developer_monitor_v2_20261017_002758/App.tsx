import React from 'react';
import { ActivityIndicator, StyleSheet, Text, View } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { AppProvider, useApp } from './src/context/AppContext';
import { LoginScreen } from './src/screens/auth/LoginScreen';
import { RegisterScreen } from './src/screens/auth/RegisterScreen';
import { VerifyEmailScreen } from './src/screens/auth/VerifyEmailScreen';
import { ForgotPasswordScreen } from './src/screens/auth/ForgotPasswordScreen';
import { DashboardScreen } from './src/screens/app/DashboardScreen';
import { ProjectsScreen } from './src/screens/app/ProjectsScreen';
import { CreateProjectScreen } from './src/screens/app/CreateProjectScreen';
import { ProjectDetailsScreen } from './src/screens/app/ProjectDetailsScreen';
import { SyncCenterScreen } from './src/screens/app/SyncCenterScreen';
import { NotificationsScreen } from './src/screens/app/NotificationsScreen';
import { SettingsScreen } from './src/screens/app/SettingsScreen';
import { colors } from './src/theme/colors';

function Router() {
  const { booting, screen } = useApp();

  if (booting) {
    return (
      <View style={styles.boot}>
        <ActivityIndicator size="large" color={colors.blue} />
        <Text style={styles.bootText}>Starting AfriSync Mobile...</Text>
      </View>
    );
  }

  switch (screen) {
    case 'register':
      return <RegisterScreen />;
    case 'verify-email':
      return <VerifyEmailScreen />;
    case 'forgot-password':
      return <ForgotPasswordScreen />;
    case 'dashboard':
      return <DashboardScreen />;
    case 'projects':
      return <ProjectsScreen />;
    case 'create-project':
      return <CreateProjectScreen />;
    case 'project-details':
      return <ProjectDetailsScreen />;
    case 'sync-center':
      return <SyncCenterScreen />;
    case 'notifications':
      return <NotificationsScreen />;
    case 'settings':
      return <SettingsScreen />;
    case 'login':
    default:
      return <LoginScreen />;
  }
}

export default function App() {
  return (
    <SafeAreaProvider>
      <AppProvider>
        <StatusBar style="dark" />
        <Router />
      </AppProvider>
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({
  boot: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.slate50,
    gap: 14
  },
  bootText: {
    color: colors.slate700,
    fontWeight: '800'
  }
});
