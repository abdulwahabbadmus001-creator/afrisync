import React, { useCallback, useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { BottomNav } from '../../components/BottomNav';
import { Card, Screen } from '../../components/Screen';
import { StatusPill } from '../../components/StatusPill';
import { TopBar } from '../../components/TopBar';
import { useApp } from '../../context/AppContext';
import { listDeveloperProjects } from '../../services/api';
import { useTheme } from '../../theme/theme';
import type { DeveloperProject } from '../../types';
import { formatRelative } from '../../utils/format';

export function ProjectsScreen() {
  const { session, openProject } = useApp();
  const { palette } = useTheme();
  const [projects, setProjects] = useState<DeveloperProject[]>([]);
  const [loading, setLoading] = useState(false);
  const load = useCallback(async () => {
    if (!session?.syncToken) return;
    setLoading(true);
    const result = await listDeveloperProjects(session.syncToken);
    if (result.ok && result.data) setProjects(result.data);
    setLoading(false);
  }, [session?.syncToken]);
  useEffect(() => { load(); }, [load]);

  return (
    <Screen contentStyle={{ paddingTop: 32 }}>
      <TopBar title="Projects" subtitle="Registered by AfriSync CLI" right={<Pressable onPress={load}><Text style={[styles.refresh, { color: palette.primary }]}>{loading ? 'Refreshing…' : 'Refresh'}</Text></Pressable>} />
      <Text style={[styles.intro, { color: palette.textMuted }]}>Projects are created from the developer’s codebase with `afrisync init`. The mobile app is a monitoring surface, not a manual project manager.</Text>
      <View style={styles.list}>
        {projects.map(project => (
          <Pressable key={project.projectId} onPress={() => openProject(project)}>
            <Card>
              <View style={styles.row}>
                <View style={{ flex: 1 }}>
                  <Text style={[styles.name, { color: palette.text }]}>{project.name}</Text>
                  <Text style={[styles.meta, { color: palette.textMuted }]}>{[project.framework, project.language, project.runtime].filter(Boolean).join(' • ') || 'Developer project'}</Text>
                </View>
                <StatusPill label={project.lastEventAt ? 'SYNCED' : 'WAITING'} tone={project.lastEventAt ? 'good' : 'neutral'} />
              </View>
              <View style={[styles.details, { borderTopColor: palette.border }]}>
                <Text style={[styles.detailText, { color: palette.textSubtle }]}>Branch {project.defaultBranch || '—'}</Text>
                <Text style={[styles.detailText, { color: palette.textSubtle }]}>Last activity {formatRelative(project.lastEventAt)}</Text>
              </View>
            </Card>
          </Pressable>
        ))}
        {!projects.length && !loading ? <Card><Text style={[styles.name, { color: palette.text }]}>No projects connected</Text><Text style={[styles.meta, { color: palette.textMuted }]}>Run `afrisync init` inside your project directory, then refresh this screen.</Text></Card> : null}
      </View>
      <BottomNav active="projects" />
    </Screen>
  );
}

const styles = StyleSheet.create({
  refresh: { fontSize: 12, fontWeight: '900' }, intro: { fontSize: 13, lineHeight: 20, marginBottom: 16 }, list: { gap: 10 },
  row: { flexDirection: 'row', alignItems: 'flex-start', gap: 12 }, name: { fontSize: 16, fontWeight: '900' }, meta: { fontSize: 12, marginTop: 5, lineHeight: 18 },
  details: { borderTopWidth: 1, paddingTop: 12, marginTop: 13, flexDirection: 'row', justifyContent: 'space-between', gap: 12 }, detailText: { fontSize: 10.5, fontWeight: '700', flex: 1 }
});
