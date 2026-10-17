import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { BottomNav } from '../../components/BottomNav';
import { Card, Screen } from '../../components/Screen';
import { StatusPill } from '../../components/StatusPill';
import { TopBar } from '../../components/TopBar';
import { useApp } from '../../context/AppContext';
import { healthCheck, listDeveloperProjectEvents, listDeveloperProjects } from '../../services/api';
import { useTheme } from '../../theme/theme';
import type { DeveloperEvent, DeveloperProject } from '../../types';
import { eventLabel, eventTone, formatRelative, isActiveSession } from '../../utils/format';

type MetricKey = 'connected' | 'active' | 'synced' | 'events';

export function DashboardScreen() {
  const { session, openProject, setScreen } = useApp();
  const { palette } = useTheme();
  const [projects, setProjects] = useState<DeveloperProject[]>([]);
  const [events, setEvents] = useState<Array<DeveloperEvent & { projectName: string }>>([]);
  const [activeProjectIds, setActiveProjectIds] = useState<string[]>([]);
  const [backendOnline, setBackendOnline] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [selectedMetric, setSelectedMetric] = useState<MetricKey | null>(null);

  const refresh = useCallback(async () => {
    if (!session?.syncToken) return;
    setRefreshing(true);
    try {
      const [health, projectResult] = await Promise.all([healthCheck(), listDeveloperProjects(session.syncToken)]);
      setBackendOnline(Boolean(health.ok && health.data?.database_ok !== false));
      const nextProjects = projectResult.ok && projectResult.data ? projectResult.data : [];
      setProjects(nextProjects);

      const eventSets = await Promise.all(nextProjects.map(async project => {
        const result = await listDeveloperProjectEvents(session.syncToken, project.projectId, 12);
        return { project, events: result.ok && result.data ? result.data : [] };
      }));

      setActiveProjectIds(eventSets.filter(set => isActiveSession(set.events)).map(set => set.project.projectId));
      setEvents(
        eventSets
          .flatMap(set => set.events.map(event => ({ ...event, projectName: set.project.name })))
          .sort((a, b) => new Date(b.occurredAt).getTime() - new Date(a.occurredAt).getTime())
          .slice(0, 8)
      );
    } finally {
      setRefreshing(false);
    }
  }, [session?.syncToken]);

  useEffect(() => { refresh(); }, [refresh]);

  const syncedProjects = useMemo(() => projects.filter(project => Boolean(project.lastEventAt)), [projects]);
  const activeProjects = useMemo(
    () => projects.filter(project => activeProjectIds.includes(project.projectId)),
    [projects, activeProjectIds]
  );

  const toggleMetric = (metric: MetricKey) => {
    setSelectedMetric(current => current === metric ? null : metric);
  };

  return (
    <Screen contentStyle={{ paddingTop: 32 }}>
      <TopBar
        title="Developer overview"
        subtitle={`Welcome, ${session?.username || 'developer'}`}
        right={
          <Pressable onPress={refresh} style={[styles.activityButton, { borderColor: palette.border, backgroundColor: palette.surface }]}>
            <Text style={[styles.activityButtonText, { color: palette.text }]}>{refreshing ? 'Refreshing…' : 'Refresh'}</Text>
          </Pressable>
        }
      />

      <View style={[styles.hero, { backgroundColor: palette.surfaceStrong, borderColor: palette.borderStrong }]}>
        <View style={styles.heroTop}>
          <View style={{ flex: 1 }}>
            <Text style={[styles.heroEyebrow, { color: palette.emerald }]}>AFRISYNC DEVELOPER PLATFORM</Text>
            <Text style={[styles.heroTitle, { color: palette.white }]}>Development activity, without the manual admin.</Text>
          </View>
          <StatusPill label={backendOnline ? 'ONLINE' : 'OFFLINE'} tone={backendOnline ? 'good' : 'bad'} />
        </View>
        <Text style={styles.heroCopy}>Projects appear here when the AfriSync CLI registers them. Sessions and events update from your codebase automatically.</Text>
      </View>

      <View style={styles.metricsGrid}>
        <View style={styles.metricRow}>
          <Metric
            label="Connected projects"
            value={String(projects.length)}
            selected={selectedMetric === 'connected'}
            onPress={() => toggleMetric('connected')}
          />
          <Metric
            label="Active sessions"
            value={String(activeProjects.length)}
            accent="amber"
            selected={selectedMetric === 'active'}
            onPress={() => toggleMetric('active')}
          />
        </View>
        <View style={styles.metricRow}>
          <Metric
            label="Synced projects"
            value={String(syncedProjects.length)}
            accent="emerald"
            selected={selectedMetric === 'synced'}
            onPress={() => toggleMetric('synced')}
          />
          <Metric
            label="Recent events"
            value={String(events.length)}
            accent="blue"
            selected={selectedMetric === 'events'}
            onPress={() => toggleMetric('events')}
          />
        </View>
      </View>

      {selectedMetric ? (
        <MetricDetails
          metric={selectedMetric}
          projects={projects}
          activeProjects={activeProjects}
          syncedProjects={syncedProjects}
          events={events}
          openProject={openProject}
        />
      ) : null}

      <View style={styles.sectionHeader}>
        <Text style={[styles.sectionTitle, { color: palette.text }]}>Projects</Text>
        <Pressable onPress={() => setScreen('projects')}><Text style={[styles.sectionLink, { color: palette.primary }]}>View all</Text></Pressable>
      </View>

      {projects.slice(0, 3).map(project => (
        <Pressable key={project.projectId} onPress={() => openProject(project)} style={({ pressed }) => [{ opacity: pressed ? 0.85 : 1 }]}>
          <Card style={styles.projectCard}>
            <View style={styles.projectTop}>
              <View style={{ flex: 1 }}>
                <Text style={[styles.projectName, { color: palette.text }]}>{project.name}</Text>
                <Text style={[styles.projectMeta, { color: palette.textMuted }]}>{[project.framework, project.language, project.runtime].filter(Boolean).join(' • ') || 'Developer project'}</Text>
              </View>
              <StatusPill label={project.lastEventAt ? 'SYNCED' : 'WAITING'} tone={project.lastEventAt ? 'good' : 'neutral'} />
            </View>
            <Text style={[styles.lastActivity, { color: palette.textSubtle }]}>Last activity {formatRelative(project.lastEventAt)}</Text>
          </Card>
        </Pressable>
      ))}
      {!projects.length ? <Card><Text style={[styles.emptyTitle, { color: palette.text }]}>No projects connected yet</Text><Text style={[styles.emptyCopy, { color: palette.textMuted }]}>Run `afrisync init` inside a codebase. The project will appear here automatically.</Text></Card> : null}

      <View style={styles.sectionHeader}>
        <Text style={[styles.sectionTitle, { color: palette.text }]}>Recent activity</Text>
        <Pressable onPress={() => setScreen('notifications')}><Text style={[styles.sectionLink, { color: palette.primary }]}>Open feed</Text></Pressable>
      </View>
      <Card>
        {events.map((event, index) => (
          <View key={`${event.eventId}-${index}`} style={[styles.eventRow, index > 0 && { borderTopColor: palette.border, borderTopWidth: 1 }]}>
            <View style={[styles.eventMark, { backgroundColor: eventTone(event.eventType) === 'bad' ? palette.red : eventTone(event.eventType) === 'warn' ? palette.amber : eventTone(event.eventType) === 'good' ? palette.emerald : palette.primary }]} />
            <View style={{ flex: 1 }}>
              <Text style={[styles.eventTitle, { color: palette.text }]}>{eventLabel(event.eventType)}</Text>
              <Text style={[styles.eventMeta, { color: palette.textSubtle }]}>{event.projectName} • {formatRelative(event.occurredAt)}</Text>
            </View>
          </View>
        ))}
        {!events.length ? <Text style={[styles.emptyCopy, { color: palette.textMuted }]}>No development activity has been recorded yet.</Text> : null}
      </Card>
      <BottomNav active="dashboard" />
    </Screen>
  );
}

function Metric({
  label,
  value,
  accent = 'blue',
  selected,
  onPress
}: {
  label: string;
  value: string;
  accent?: 'blue' | 'emerald' | 'amber';
  selected: boolean;
  onPress: () => void;
}) {
  const { palette } = useTheme();
  const color = accent === 'emerald' ? palette.emerald : accent === 'amber' ? palette.amber : palette.primary;

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ selected }}
      onPress={onPress}
      style={({ pressed }) => [
        styles.metric,
        {
          backgroundColor: selected ? palette.surfaceAlt : palette.surface,
          borderColor: selected ? color : palette.border,
          opacity: pressed ? 0.82 : 1
        }
      ]}
    >
      <View style={styles.metricHeader}>
        <Text style={[styles.metricValue, { color }]}>{value}</Text>
        <Text style={[styles.metricChevron, { color }]}>{selected ? '−' : '›'}</Text>
      </View>
      <Text style={[styles.metricLabel, { color: palette.textMuted }]}>{label}</Text>
      <Text style={[styles.metricHint, { color: palette.textSubtle }]}>{selected ? 'Tap to close' : 'Tap to view'}</Text>
    </Pressable>
  );
}

function MetricDetails({
  metric,
  projects,
  activeProjects,
  syncedProjects,
  events,
  openProject
}: {
  metric: MetricKey;
  projects: DeveloperProject[];
  activeProjects: DeveloperProject[];
  syncedProjects: DeveloperProject[];
  events: Array<DeveloperEvent & { projectName: string }>;
  openProject: (project: DeveloperProject) => void;
}) {
  const { palette } = useTheme();

  const config = {
    connected: { title: 'Connected projects', items: projects },
    active: { title: 'Active sessions', items: activeProjects },
    synced: { title: 'Synced projects', items: syncedProjects }
  } as const;

  if (metric === 'events') {
    return (
      <View style={[styles.metricDetails, { backgroundColor: palette.surface, borderColor: palette.border }]}>
        <Text style={[styles.metricDetailsTitle, { color: palette.text }]}>Recent events</Text>
        {events.length ? events.map((event, index) => (
          <View key={`${event.eventId}-${index}`} style={[styles.detailRow, index > 0 && { borderTopWidth: 1, borderTopColor: palette.border }]}>
            <View style={[styles.eventMark, { backgroundColor: eventTone(event.eventType) === 'bad' ? palette.red : eventTone(event.eventType) === 'warn' ? palette.amber : eventTone(event.eventType) === 'good' ? palette.emerald : palette.primary }]} />
            <View style={{ flex: 1 }}>
              <Text style={[styles.detailTitle, { color: palette.text }]}>{eventLabel(event.eventType)}</Text>
              <Text style={[styles.detailMeta, { color: palette.textSubtle }]}>{event.projectName} • {formatRelative(event.occurredAt)}</Text>
            </View>
          </View>
        )) : <Text style={[styles.emptyCopy, { color: palette.textMuted }]}>No recent events to display.</Text>}
      </View>
    );
  }

  const current = config[metric];
  return (
    <View style={[styles.metricDetails, { backgroundColor: palette.surface, borderColor: palette.border }]}>
      <Text style={[styles.metricDetailsTitle, { color: palette.text }]}>{current.title}</Text>
      {current.items.length ? current.items.map((project, index) => (
        <Pressable
          key={project.projectId}
          onPress={() => openProject(project)}
          style={({ pressed }) => [styles.detailRow, index > 0 && { borderTopWidth: 1, borderTopColor: palette.border }, { opacity: pressed ? 0.72 : 1 }]}
        >
          <View style={{ flex: 1 }}>
            <Text style={[styles.detailTitle, { color: palette.text }]}>{project.name}</Text>
            <Text style={[styles.detailMeta, { color: palette.textSubtle }]}>
              {[project.framework, project.language, project.runtime].filter(Boolean).join(' • ') || 'Developer project'}
            </Text>
          </View>
          <Text style={[styles.detailOpen, { color: palette.primary }]}>Open</Text>
        </Pressable>
      )) : <Text style={[styles.emptyCopy, { color: palette.textMuted }]}>Nothing to display in this category yet.</Text>}
    </View>
  );
}

const styles = StyleSheet.create({
  activityButton: { borderWidth: 1, borderRadius: 12, paddingHorizontal: 12, paddingVertical: 9 },
  activityButtonText: { fontSize: 11.5, fontWeight: '900' },
  hero: { borderRadius: 22, padding: 19, borderWidth: 1 },
  heroTop: { flexDirection: 'row', alignItems: 'flex-start', gap: 12 },
  heroEyebrow: { fontSize: 10.5, fontWeight: '900', letterSpacing: 1.05 },
  heroTitle: { fontSize: 24, fontWeight: '900', letterSpacing: -0.6, lineHeight: 29, marginTop: 7 },
  heroCopy: { color: '#AEBBCD', lineHeight: 19, fontSize: 13, marginTop: 11 },

  metricsGrid: { marginTop: 14, gap: 10 },
  metricRow: { flexDirection: 'row', gap: 10, width: '100%' },
  metric: { flex: 1, minWidth: 0, minHeight: 126, borderWidth: 1, borderRadius: 17, padding: 15, justifyContent: 'space-between' },
  metricHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start' },
  metricValue: { fontSize: 27, fontWeight: '900', letterSpacing: -0.6 },
  metricChevron: { fontSize: 25, fontWeight: '700', lineHeight: 28 },
  metricLabel: { fontSize: 11.5, fontWeight: '800', marginTop: 5 },
  metricHint: { fontSize: 9.5, fontWeight: '700', marginTop: 8 },
  metricDetails: { borderWidth: 1, borderRadius: 17, paddingHorizontal: 15, paddingVertical: 14, marginTop: 10 },
  metricDetailsTitle: { fontSize: 14.5, fontWeight: '900', marginBottom: 6 },
  detailRow: { minHeight: 54, flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 11 },
  detailTitle: { fontSize: 13, fontWeight: '800' },
  detailMeta: { fontSize: 11, marginTop: 3 },
  detailOpen: { fontSize: 11.5, fontWeight: '900' },

  sectionHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: 24, marginBottom: 10 },
  sectionTitle: { fontSize: 19, fontWeight: '900', letterSpacing: -0.25 },
  sectionLink: { fontSize: 12, fontWeight: '900' },
  projectCard: { marginBottom: 10 },
  projectTop: { flexDirection: 'row', gap: 12, alignItems: 'flex-start' },
  projectName: { fontSize: 16, fontWeight: '900' },
  projectMeta: { fontSize: 12, marginTop: 4 },
  lastActivity: { fontSize: 11.5, marginTop: 13, fontWeight: '700' },
  eventRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 12, gap: 11 },
  eventMark: { width: 8, height: 8, borderRadius: 999 },
  eventTitle: { fontSize: 13.5, fontWeight: '800' },
  eventMeta: { fontSize: 11.5, marginTop: 3 },
  emptyTitle: { fontSize: 16, fontWeight: '900' },
  emptyCopy: { fontSize: 12.5, lineHeight: 19, marginTop: 6 }
});
