import React, { useCallback, useState } from 'react';
import { Alert, StyleSheet, Text, View } from 'react-native';
import { AppButton } from '../../components/AppButton';
import { Card, Screen } from '../../components/Screen';
import { TopBar } from '../../components/TopBar';
import { useApp } from '../../context/AppContext';
import { getPendingQueue } from '../../storage/db';
import { runMobileSync, type SyncReport } from '../../services/syncService';
import { colors } from '../../theme/colors';

export function SyncCenterScreen() {
  const { session, setScreen } = useApp();
  const [queue, setQueue] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [lastReport, setLastReport] = useState<SyncReport | null>(null);

  const refresh = useCallback(async () => {
    setQueue(await getPendingQueue());
  }, []);

  React.useEffect(() => {
    refresh();
  }, [refresh]);

  async function syncNow() {
    setLoading(true);
    const report = await runMobileSync(session);
    setLastReport(report);
    await refresh();
    setLoading(false);
    Alert.alert('Sync report', report.offline ? 'Device is offline. Changes remain safe locally.' : `${report.synced} synced, ${report.failed} failed.`);
  }

  return (
    <Screen>
      <TopBar title="Sync Center" onBack={() => setScreen('dashboard')} />
      <Card>
        <Text style={styles.count}>{queue.length}</Text>
        <Text style={styles.label}>queued mobile change(s)</Text>
        <AppButton title="Sync now" loading={loading} onPress={syncNow} style={{ marginTop: 16 }} />
      </Card>

      {lastReport ? (
        <View style={styles.report}>
          <Text style={styles.reportTitle}>Last sync report</Text>
          <Text style={styles.reportText}>Attempted: {lastReport.attempted}</Text>
          <Text style={styles.reportText}>Synced: {lastReport.synced}</Text>
          <Text style={styles.reportText}>Failed: {lastReport.failed}</Text>
          <Text style={styles.reportText}>Offline: {lastReport.offline ? 'Yes' : 'No'}</Text>
        </View>
      ) : null}

      <View style={styles.list}>
        {queue.map((item) => (
          <View key={item.id} style={styles.item}>
            <Text style={styles.itemTitle}>{item.entity_type.toUpperCase()} • {item.operation}</Text>
            <Text style={styles.itemText}>{item.entity_uuid}</Text>
            {item.last_error ? <Text style={styles.error}>{item.last_error}</Text> : null}
          </View>
        ))}
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  count: { color: colors.blue, fontWeight: '900', fontSize: 42 },
  label: { color: colors.slate600, fontWeight: '800' },
  report: { backgroundColor: colors.slate950, borderRadius: 22, padding: 16, marginTop: 18 },
  reportTitle: { color: colors.white, fontWeight: '900', marginBottom: 8 },
  reportText: { color: '#CBD5E1', marginTop: 4 },
  list: { gap: 10, marginTop: 18 },
  item: { backgroundColor: colors.white, borderWidth: 1, borderColor: colors.slate200, borderRadius: 18, padding: 14 },
  itemTitle: { color: colors.slate950, fontWeight: '900' },
  itemText: { color: colors.slate500, marginTop: 4, fontSize: 12 },
  error: { color: colors.red, marginTop: 8, fontWeight: '700' }
});
