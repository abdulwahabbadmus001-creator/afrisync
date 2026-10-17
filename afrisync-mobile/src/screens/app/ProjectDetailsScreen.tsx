import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Card, Screen } from '../../components/Screen';
import { StatusPill } from '../../components/StatusPill';
import { TopBar } from '../../components/TopBar';
import { useApp } from '../../context/AppContext';
import { listDeveloperProjectEvents } from '../../services/api';
import { useTheme } from '../../theme/theme';
import type { DeveloperEvent } from '../../types';
import { eventLabel, eventTone, formatDateTime, formatRelative, isActiveSession } from '../../utils/format';

export function ProjectDetailsScreen() {
  const { session, selectedProject, setScreen } = useApp();
  const { palette } = useTheme();
  const [events, setEvents] = useState<DeveloperEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const load = useCallback(async () => {
    if (!session?.syncToken || !selectedProject) return;
    setLoading(true);
    const result = await listDeveloperProjectEvents(session.syncToken, selectedProject.projectId, 80);
    if (result.ok && result.data) setEvents(result.data);
    setLoading(false);
  }, [session?.syncToken, selectedProject]);
  useEffect(() => { load(); }, [load]);

  const active = useMemo(() => isActiveSession(events), [events]);
  const latest = events[0];
  const lastEnd = events.find(event => event.eventType === 'development.session.ended');

  if (!selectedProject) return <Screen><TopBar title="Project" onBack={() => setScreen('projects')} /><Text style={{ color: palette.textMuted }}>No project selected.</Text></Screen>;

  return (
    <Screen contentStyle={{ paddingTop: 32 }}>
      <TopBar title={selectedProject.name} subtitle="Developer project" onBack={() => setScreen('projects')} right={<Pressable onPress={load}><Text style={[styles.refresh, { color: palette.primary }]}>{loading ? 'Refreshing…' : 'Refresh'}</Text></Pressable>} />
      <Card strong>
        <View style={styles.topRow}>
          <View style={{ flex: 1 }}>
            <Text style={[styles.kicker, { color: palette.emerald }]}>PROJECT STATUS</Text>
            <Text style={styles.heroName}>{selectedProject.name}</Text>
          </View>
          <StatusPill label={active ? 'ACTIVE SESSION' : 'SYNCED'} tone={active ? 'warn' : 'good'} />
        </View>
        <Text style={styles.heroMeta}>{[selectedProject.framework, selectedProject.language, selectedProject.runtime].filter(Boolean).join(' • ') || 'Developer integration'}</Text>
      </Card>

      <View style={styles.infoGrid}>
        <Info label="Last activity" value={formatRelative(latest?.occurredAt || selectedProject.lastEventAt)} />
        <Info label="Last session" value={lastEnd ? formatRelative(lastEnd.occurredAt) : active ? 'Running now' : 'No completed session'} />
        <Info label="Branch" value={selectedProject.defaultBranch || '—'} />
        <Info label="Events" value={String(events.length)} />
      </View>

      <Text style={[styles.section, { color: palette.text }]}>Activity timeline</Text>
      <Card>
        {events.map((event, index) => (
          <View key={`${event.eventId}-${index}`} style={[styles.event, index > 0 && { borderTopColor: palette.border, borderTopWidth: 1 }]}>
            <View style={[styles.lineDot, { backgroundColor: eventTone(event.eventType) === 'bad' ? palette.red : eventTone(event.eventType) === 'warn' ? palette.amber : eventTone(event.eventType) === 'good' ? palette.emerald : palette.primary }]} />
            <View style={{ flex: 1 }}>
              <Text style={[styles.eventTitle, { color: palette.text }]}>{eventLabel(event.eventType)}</Text>
              <Text style={[styles.eventMeta, { color: palette.textSubtle }]}>{formatDateTime(event.occurredAt)} • {event.source}</Text>
            </View>
          </View>
        ))}
        {!events.length ? <Text style={[styles.empty, { color: palette.textMuted }]}>No events recorded for this project yet.</Text> : null}
      </Card>
    </Screen>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  const { palette } = useTheme();
  return <View style={[styles.info, { backgroundColor: palette.surface, borderColor: palette.border }]}><Text style={[styles.infoLabel, { color: palette.textSubtle }]}>{label}</Text><Text style={[styles.infoValue, { color: palette.text }]} numberOfLines={2}>{value}</Text></View>;
}

const styles = StyleSheet.create({
  refresh: { fontSize: 12, fontWeight: '900' }, topRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 12 }, kicker: { fontSize: 10.5, fontWeight: '900', letterSpacing: 1.0 },
  heroName: { color: '#FFFFFF', fontSize: 24, fontWeight: '900', marginTop: 6, letterSpacing: -0.5 }, heroMeta: { color: '#AEBBCD', fontSize: 12.5, marginTop: 12 },
  infoGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, marginTop: 14 }, info: { width: '48.5%', borderWidth: 1, borderRadius: 16, padding: 14 }, infoLabel: { fontSize: 10.5, fontWeight: '800' }, infoValue: { fontSize: 14, fontWeight: '900', marginTop: 5, lineHeight: 18 },
  section: { fontSize: 19, fontWeight: '900', marginTop: 24, marginBottom: 10 }, event: { flexDirection: 'row', gap: 11, paddingVertical: 13, alignItems: 'flex-start' }, lineDot: { width: 8, height: 8, borderRadius: 999, marginTop: 5 },
  eventTitle: { fontSize: 13.5, fontWeight: '800' }, eventMeta: { fontSize: 11, marginTop: 4, lineHeight: 16 }, empty: { fontSize: 12.5, lineHeight: 19 }
});
