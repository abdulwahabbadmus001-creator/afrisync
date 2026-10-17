import React, { useCallback, useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Card, Screen } from '../../components/Screen';
import { TopBar } from '../../components/TopBar';
import { useApp } from '../../context/AppContext';
import { listDeveloperProjectEvents, listDeveloperProjects } from '../../services/api';
import { useTheme } from '../../theme/theme';
import type { DeveloperEvent } from '../../types';
import { eventLabel, eventTone, formatDateTime } from '../../utils/format';

export function NotificationsScreen() {
  const { session, setScreen } = useApp();
  const { palette } = useTheme();
  const [events, setEvents] = useState<Array<DeveloperEvent & { projectName: string }>>([]);
  const [loading, setLoading] = useState(false);
  const load = useCallback(async () => {
    if (!session?.syncToken) return;
    setLoading(true);
    const projects = await listDeveloperProjects(session.syncToken);
    const list = projects.ok && projects.data ? projects.data : [];
    const sets = await Promise.all(list.map(async project => {
      const result = await listDeveloperProjectEvents(session.syncToken, project.projectId, 40);
      return (result.ok && result.data ? result.data : []).map(event => ({ ...event, projectName: project.name }));
    }));
    setEvents(sets.flat().sort((a, b) => new Date(b.occurredAt).getTime() - new Date(a.occurredAt).getTime()).slice(0, 50));
    setLoading(false);
  }, [session?.syncToken]);
  useEffect(() => { load(); }, [load]);

  return (
    <Screen contentStyle={{ paddingTop: 32 }}>
      <TopBar title="Activity feed" subtitle="Events from connected projects" onBack={() => setScreen('dashboard')} right={<Pressable onPress={load}><Text style={[styles.refresh, { color: palette.primary }]}>{loading ? 'Refreshing…' : 'Refresh'}</Text></Pressable>} />
      <View style={styles.list}>
        {events.map((event, index) => {
          const tone = eventTone(event.eventType);
          const mark = tone === 'bad' ? palette.red : tone === 'warn' ? palette.amber : tone === 'good' ? palette.emerald : palette.primary;
          return <Card key={`${event.eventId}-${index}`} style={styles.card}><View style={styles.row}><View style={[styles.mark, { backgroundColor: mark }]} /><View style={{ flex: 1 }}><Text style={[styles.title, { color: palette.text }]}>{eventLabel(event.eventType)}</Text><Text style={[styles.project, { color: palette.textMuted }]}>{event.projectName}</Text><Text style={[styles.meta, { color: palette.textSubtle }]}>{formatDateTime(event.occurredAt)} • {event.source}</Text></View></View></Card>;
        })}
        {!events.length && !loading ? <Card><Text style={[styles.title, { color: palette.text }]}>No activity yet</Text><Text style={[styles.project, { color: palette.textMuted }]}>Tracked CLI events will appear here automatically.</Text></Card> : null}
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({ refresh: { fontSize: 12, fontWeight: '900' }, list: { gap: 9 }, card: { padding: 15 }, row: { flexDirection: 'row', gap: 11 }, mark: { width: 8, height: 8, borderRadius: 999, marginTop: 5 }, title: { fontSize: 14, fontWeight: '900' }, project: { fontSize: 12, marginTop: 4 }, meta: { fontSize: 10.5, marginTop: 6 } });
