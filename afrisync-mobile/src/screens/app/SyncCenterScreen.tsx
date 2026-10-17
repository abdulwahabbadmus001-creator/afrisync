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
import { eventLabel, formatRelative, isActiveSession } from '../../utils/format';

type SyncMetricKey = 'projects' | 'active' | 'synced' | 'latest';
type ProjectState = 'ACTIVE' | 'SYNCED' | 'WAITING';
type EventWithProject = DeveloperEvent & { projectName: string; projectId: string };

export function SyncCenterScreen() {
  const { session, openProject } = useApp();
  const { palette } = useTheme();
  const [projects, setProjects] = useState<DeveloperProject[]>([]);
  const [states, setStates] = useState<Record<string, ProjectState>>({});
  const [events, setEvents] = useState<EventWithProject[]>([]);
  const [healthy, setHealthy] = useState(false);
  const [latest, setLatest] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [selectedMetric, setSelectedMetric] = useState<SyncMetricKey | null>(null);

  const load = useCallback(async () => {
    if (!session?.syncToken) return;
    setLoading(true);
    try {
      const [health, projectResult] = await Promise.all([
        healthCheck(),
        listDeveloperProjects(session.syncToken)
      ]);

      setHealthy(Boolean(health.ok && health.data?.database_ok !== false));
      const nextProjects = projectResult.ok && projectResult.data ? projectResult.data : [];
      setProjects(nextProjects);

      const eventSets = await Promise.all(
        nextProjects.map(async project => {
          const result = await listDeveloperProjectEvents(session.syncToken, project.projectId, 20);
          return {
            project,
            events: result.ok && result.data ? result.data : []
          };
        })
      );

      const nextStates: Record<string, ProjectState> = {};
      let newest: string | null = null;
      const allEvents: EventWithProject[] = [];

      for (const { project, events: projectEvents } of eventSets) {
        nextStates[project.projectId] = isActiveSession(projectEvents)
          ? 'ACTIVE'
          : project.lastEventAt
            ? 'SYNCED'
            : 'WAITING';

        const candidate = projectEvents[0]?.occurredAt || project.lastEventAt || null;
        if (candidate && (!newest || new Date(candidate).getTime() > new Date(newest).getTime())) {
          newest = candidate;
        }

        allEvents.push(
          ...projectEvents.map(event => ({
            ...event,
            projectName: project.name,
            projectId: project.projectId
          }))
        );
      }

      setStates(nextStates);
      setLatest(newest);
      setEvents(
        allEvents
          .sort((a, b) => new Date(b.occurredAt).getTime() - new Date(a.occurredAt).getTime())
          .slice(0, 12)
      );
    } finally {
      setLoading(false);
    }
  }, [session?.syncToken]);

  useEffect(() => { load(); }, [load]);

  const activeProjects = useMemo(
    () => projects.filter(project => states[project.projectId] === 'ACTIVE'),
    [projects, states]
  );
  const syncedProjects = useMemo(
    () => projects.filter(project => states[project.projectId] === 'SYNCED'),
    [projects, states]
  );

  const toggleMetric = (metric: SyncMetricKey) => {
    setSelectedMetric(current => current === metric ? null : metric);
  };

  return (
    <Screen contentStyle={{ paddingTop: 32 }}>
      <TopBar
        title="Sync center"
        subtitle="Automatic developer sync"
        right={
          <Pressable onPress={load} hitSlop={8}>
            <Text style={[styles.refresh, { color: palette.primary }]}>
              {loading ? 'Refreshing…' : 'Refresh'}
            </Text>
          </Pressable>
        }
      />

      <Card strong style={styles.healthCard}>
        <View style={styles.healthRow}>
          <View style={{ flex: 1 }}>
            <Text style={[styles.kicker, { color: palette.emerald }]}>SYNC HEALTH</Text>
            <Text style={styles.healthTitle}>{healthy ? 'All systems operational' : 'Backend unavailable'}</Text>
          </View>
          <StatusPill label={healthy ? 'HEALTHY' : 'OFFLINE'} tone={healthy ? 'good' : 'bad'} />
        </View>
        <Text style={styles.healthCopy}>
          AfriSync queues development activity when connectivity drops and retries when the backend becomes reachable again.
        </Text>
      </Card>

      <View style={styles.metricsGrid}>
        <View style={styles.metricRow}>
          <Metric
            value={String(projects.length)}
            label="Projects"
            selected={selectedMetric === 'projects'}
            onPress={() => toggleMetric('projects')}
          />
          <Metric
            value={String(activeProjects.length)}
            label="Active"
            tone="warn"
            selected={selectedMetric === 'active'}
            onPress={() => toggleMetric('active')}
          />
        </View>
        <View style={styles.metricRow}>
          <Metric
            value={String(syncedProjects.length)}
            label="Synced"
            tone="good"
            selected={selectedMetric === 'synced'}
            onPress={() => toggleMetric('synced')}
          />
          <Metric
            value={formatRelative(latest)}
            label="Latest event"
            small
            selected={selectedMetric === 'latest'}
            onPress={() => toggleMetric('latest')}
          />
        </View>
      </View>

      {selectedMetric ? (
        <SyncMetricDetails
          metric={selectedMetric}
          projects={projects}
          activeProjects={activeProjects}
          syncedProjects={syncedProjects}
          events={events}
          states={states}
          openProject={openProject}
        />
      ) : null}

      <Text style={[styles.section, { color: palette.text }]}>Project sync state</Text>
      <View style={styles.list}>
        {projects.map(project => {
          const state = states[project.projectId] || 'WAITING';
          return (
            <Pressable
              key={project.projectId}
              onPress={() => openProject(project)}
              style={({ pressed }) => ({ opacity: pressed ? 0.84 : 1 })}
            >
              <Card style={styles.projectCard}>
                <View style={styles.projectRow}>
                  <View style={{ flex: 1 }}>
                    <Text style={[styles.name, { color: palette.text }]}>{project.name}</Text>
                    <Text style={[styles.meta, { color: palette.textSubtle }]}>Last activity {formatRelative(project.lastEventAt)}</Text>
                  </View>
                  <StatusPill
                    label={state}
                    tone={state === 'ACTIVE' ? 'warn' : state === 'SYNCED' ? 'good' : 'neutral'}
                  />
                </View>
              </Card>
            </Pressable>
          );
        })}
        {!projects.length && !loading ? (
          <Card><Text style={[styles.empty, { color: palette.textMuted }]}>No projects have been registered yet.</Text></Card>
        ) : null}
      </View>

      <BottomNav active="sync-center" />
    </Screen>
  );
}

function Metric({
  value,
  label,
  tone = 'info',
  small = false,
  selected,
  onPress
}: {
  value: string;
  label: string;
  tone?: 'info' | 'good' | 'warn';
  small?: boolean;
  selected: boolean;
  onPress: () => void;
}) {
  const { palette } = useTheme();
  const color = tone === 'good' ? palette.emerald : tone === 'warn' ? palette.amber : palette.primary;

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`View ${label}`}
      accessibilityState={{ selected }}
      hitSlop={4}
      onPress={onPress}
      style={({ pressed }) => [
        styles.metric,
        {
          backgroundColor: selected ? palette.surfaceAlt : palette.surface,
          borderColor: selected ? color : palette.border,
          opacity: pressed ? 0.78 : 1
        }
      ]}
    >
      <View style={styles.metricTop}>
        <Text style={[small ? styles.metricSmall : styles.metricValue, { color }]} numberOfLines={1}>{value}</Text>
        <Text style={[styles.chevron, { color }]}>{selected ? '−' : '›'}</Text>
      </View>
      <Text style={[styles.metricLabel, { color: palette.textMuted }]}>{label}</Text>
      <Text style={[styles.metricHint, { color: palette.textSubtle }]}>{selected ? 'Tap to close' : 'Tap to open'}</Text>
    </Pressable>
  );
}

function SyncMetricDetails({
  metric,
  projects,
  activeProjects,
  syncedProjects,
  events,
  states,
  openProject
}: {
  metric: SyncMetricKey;
  projects: DeveloperProject[];
  activeProjects: DeveloperProject[];
  syncedProjects: DeveloperProject[];
  events: EventWithProject[];
  states: Record<string, ProjectState>;
  openProject: (project: DeveloperProject) => void;
}) {
  const { palette } = useTheme();

  const title = metric === 'projects'
    ? 'Connected projects'
    : metric === 'active'
      ? 'Active projects'
      : metric === 'synced'
        ? 'Synced projects'
        : 'Latest development events';

  const list = metric === 'projects' ? projects : metric === 'active' ? activeProjects : syncedProjects;

  return (
    <Card style={[styles.detailsCard, { borderColor: palette.borderStrong }]}>
      <Text style={[styles.detailsTitle, { color: palette.text }]}>{title}</Text>
      <Text style={[styles.detailsCopy, { color: palette.textMuted }]}>Tap an item to open its project details.</Text>

      {metric === 'latest' ? (
        <View style={styles.detailsList}>
          {events.slice(0, 6).map(event => {
            const project = projects.find(item => item.projectId === event.projectId);
            return (
              <Pressable
                key={event.eventId}
                disabled={!project}
                onPress={() => project && openProject(project)}
                style={({ pressed }) => [styles.detailItem, { borderTopColor: palette.border, opacity: pressed ? 0.7 : 1 }]}
              >
                <View style={{ flex: 1 }}>
                  <Text style={[styles.detailName, { color: palette.text }]}>{eventLabel(event.eventType)}</Text>
                  <Text style={[styles.detailMeta, { color: palette.textSubtle }]}>{event.projectName} • {formatRelative(event.occurredAt)}</Text>
                </View>
                <Text style={[styles.openMark, { color: palette.primary }]}>›</Text>
              </Pressable>
            );
          })}
          {!events.length ? <Text style={[styles.empty, { color: palette.textMuted }]}>No events recorded yet.</Text> : null}
        </View>
      ) : (
        <View style={styles.detailsList}>
          {list.map(project => (
            <Pressable
              key={project.projectId}
              onPress={() => openProject(project)}
              style={({ pressed }) => [styles.detailItem, { borderTopColor: palette.border, opacity: pressed ? 0.7 : 1 }]}
            >
              <View style={{ flex: 1 }}>
                <Text style={[styles.detailName, { color: palette.text }]}>{project.name}</Text>
                <Text style={[styles.detailMeta, { color: palette.textSubtle }]}>Last activity {formatRelative(project.lastEventAt)}</Text>
              </View>
              <StatusPill
                label={states[project.projectId] || 'WAITING'}
                tone={states[project.projectId] === 'ACTIVE' ? 'warn' : states[project.projectId] === 'SYNCED' ? 'good' : 'neutral'}
              />
            </Pressable>
          ))}
          {!list.length ? <Text style={[styles.empty, { color: palette.textMuted }]}>Nothing to show for this metric yet.</Text> : null}
        </View>
      )}
    </Card>
  );
}

const styles = StyleSheet.create({
  refresh: { fontSize: 12, fontWeight: '900' },
  healthCard: { width: '100%' },
  healthRow: { flexDirection: 'row', gap: 12, alignItems: 'flex-start' },
  kicker: { fontSize: 10.5, fontWeight: '900', letterSpacing: 1 },
  healthTitle: { color: '#FFFFFF', fontSize: 21, fontWeight: '900', marginTop: 6, letterSpacing: -0.4 },
  healthCopy: { color: '#AEBBCD', lineHeight: 19, fontSize: 12.5, marginTop: 12 },
  metricsGrid: { width: '100%', gap: 10, marginTop: 14 },
  metricRow: { flexDirection: 'row', gap: 10, width: '100%' },
  metric: { flex: 1, minWidth: 0, minHeight: 108, borderWidth: 1, borderRadius: 16, paddingHorizontal: 16, paddingVertical: 14, justifyContent: 'space-between' },
  metricTop: { flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'space-between', gap: 6 },
  metricValue: { fontSize: 27, fontWeight: '900' },
  metricSmall: { fontSize: 16, fontWeight: '900', marginTop: 6, flexShrink: 1 },
  chevron: { fontSize: 24, fontWeight: '700', lineHeight: 27 },
  metricLabel: { fontSize: 12, fontWeight: '900', marginTop: 5 },
  metricHint: { fontSize: 9.5, fontWeight: '700', marginTop: 4 },
  detailsCard: { marginTop: 12, width: '100%', borderWidth: 1 },
  detailsTitle: { fontSize: 16, fontWeight: '900' },
  detailsCopy: { fontSize: 11.5, marginTop: 4 },
  detailsList: { marginTop: 10 },
  detailItem: { minHeight: 58, borderTopWidth: 1, flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 12 },
  detailName: { fontSize: 13.5, fontWeight: '900' },
  detailMeta: { fontSize: 10.5, marginTop: 4 },
  openMark: { fontSize: 24, fontWeight: '700' },
  section: { fontSize: 19, fontWeight: '900', marginTop: 24, marginBottom: 10 },
  list: { gap: 9, width: '100%' },
  projectCard: { padding: 15, width: '100%' },
  projectRow: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  name: { fontSize: 14.5, fontWeight: '900' },
  meta: { fontSize: 11.5, marginTop: 4 },
  empty: { fontSize: 12, lineHeight: 18, paddingVertical: 8 }
});
