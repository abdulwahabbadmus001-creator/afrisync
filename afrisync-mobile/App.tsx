import React from 'react';
import { ActivityIndicator, StyleSheet, Text, View } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { AppProvider, useApp } from './src/context/AppContext';
import { ThemeProvider, useTheme } from './src/theme/theme';
import { Brand } from './src/components/Brand';
import { BackendSetupScreen } from './src/screens/auth/BackendSetupScreen';
import { LoginScreen } from './src/screens/auth/LoginScreen';
import { RegisterScreen } from './src/screens/auth/RegisterScreen';
import { VerifyEmailScreen } from './src/screens/auth/VerifyEmailScreen';
import { ForgotPasswordScreen } from './src/screens/auth/ForgotPasswordScreen';
import { DashboardScreen } from './src/screens/app/DashboardScreen';
import { ProjectsScreen } from './src/screens/app/ProjectsScreen';
import { ProjectDetailsScreen } from './src/screens/app/ProjectDetailsScreen';
import { SyncCenterScreen } from './src/screens/app/SyncCenterScreen';
import { NotificationsScreen } from './src/screens/app/NotificationsScreen';
import { SettingsScreen } from './src/screens/app/SettingsScreen';

function Router() {
  const { booting, screen } = useApp();
  const { palette, actualMode } = useTheme();

  if (booting) {
    return (
      <View style={[styles.boot, { backgroundColor: palette.background }]}>
        <View style={styles.bootLogo}>
          <Brand auth />
        </View>
        <Text style={[styles.bootName, { color: palette.text }]}>AfriSync</Text>
        <ActivityIndicator style={styles.bootSpinner} size="small" color={palette.primary} />
        <StatusBar style={actualMode === 'dark' ? 'light' : 'dark'} />
      </View>
    );
  }

  const content = (() => {
    switch (screen) {
      case 'backend-setup': return <BackendSetupScreen />;
      case 'register': return <RegisterScreen />;
      case 'verify-email': return <VerifyEmailScreen />;
      case 'forgot-password': return <ForgotPasswordScreen />;
      case 'dashboard': return <DashboardScreen />;
      case 'projects': return <ProjectsScreen />;
      case 'project-details': return <ProjectDetailsScreen />;
      case 'sync-center': return <SyncCenterScreen />;
      case 'notifications': return <NotificationsScreen />;
      case 'settings': return <SettingsScreen />;
      default: return <LoginScreen />;
    }
  })();

  return <><StatusBar style={actualMode === 'dark' ? 'light' : 'dark'} />{content}</>;
}

export default function App() {
  return (
    <SafeAreaProvider>
      <ThemeProvider>
        <AppProvider>
          <Router />
        </AppProvider>
      </ThemeProvider>
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({
  boot: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 28 },
  bootLogo: { backgroundColor: 'transparent' },
  bootName: { fontWeight: '900', fontSize: 22, marginTop: 10, letterSpacing: -0.35 },
  bootSpinner: { marginTop: 22 }
});
