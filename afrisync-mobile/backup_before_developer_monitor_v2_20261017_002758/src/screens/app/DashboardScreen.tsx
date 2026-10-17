import React, { useCallback, useState } from 'react';
import { RefreshControl, StyleSheet, Text, View } from 'react-native';
import { AppButton } from '../../components/AppButton';
import { Screen } from '../../components/Screen';
import { StatCard } from '../../components/StatCard';
import { TopBar } from '../../components/TopBar';
import { useApp } from '../../context/AppContext';
import { getDashboardCounts } from '../../storage/db';
import { runMobileSync } from '../../services/syncService';
import { colors } from '../../theme/colors';

export function DashboardScreen() {
  const { session, setScreen, signOut } = useApp();
  const [counts, setCounts] = useState({ projects: 0, pending: 0, errors: 0, conflicts: 0, unread: 0, queued: 0 });
  const [refreshing, setRefreshing] = useState(false);

  const refresh = useCallback(async () => {
    setRefreshing(true);
    setCounts(await getDashboardCounts());
    setRefreshing(false);
  }, []);

  React.useEffect(() => {
    refresh();
  }, [refresh]);

  async function syncNow() {
    setRefreshing(true);
    await runMobileSync(session);
    await refresh();
    setRefreshing(false);
  }

  return (
    <Screen>
      <TopBar title="Overview" right={<AppButton title="Logout" variant="ghost" onPress={signOut} />} />
      <View style={styles.header}>
        <Text style={styles.greeting}>Welcome{session?.fullName ? `, ${session.fullName.split(' ')[0]}` : ''}</Text>
        <Text style={styles.subtitle}>Your mobile workspace is local-first. Create, work offline, then sync when ready.</Text>
      </View>

      <View style={styles.grid}>
        <StatCard label="Projects" value={counts.projects} accent={colors.blue} onPress={() => setScreen('projects')} />
        <StatCard label="Queued sync" value={counts.queued} accent={colors.emerald} onPress={() => setScreen('sync-center')} />
        <StatCard label="Notifications" value={counts.unread} accent={colors.amber} onPress={() => setScreen('notifications')} />
        <StatCard label="Conflicts" value={counts.conflicts} accent={colors.red} onPress={() => setScreen('sync-center')} />
      </View>

      <View style={styles.actions}>
        <AppButton title="Create project" onPress={() => setScreen('create-project')} />
        <AppButton title="Sync now" variant="secondary" loading={refreshing} onPress={syncNow} />
        <AppButton title="Settings" variant="ghost" onPress={() => setScreen('settings')} />
      </View>

      <View style={styles.panel}>
        <Text style={styles.panelTitle}>Mobile architecture</Text>
        <Text style={styles.panelText}>Projects and notes are saved first in mobile SQLite. Sync pushes queued changes to your AfriSync FastAPI backend when internet is available.</Text>
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  header: { marginBottom: 20 },
  greeting: { color: colors.slate950, fontSize: 32, fontWeight: '900', letterSpacing: -1 },
  subtitle: { color: colors.slate600, fontSize: 15, lineHeight: 22, marginTop: 6 },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: 12, justifyContent: 'space-between' },
  actions: { gap: 12, marginTop: 22 },
  panel: { marginTop: 22, backgroundColor: colors.slate950, borderRadius: 24, padding: 18 },
  panelTitle: { color: colors.white, fontSize: 18, fontWeight: '900', marginBottom: 8 },
  panelText: { color: '#CBD5E1', fontSize: 14, lineHeight: 21 }
});
