import React, { useCallback, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { AppButton } from '../../components/AppButton';
import { Screen } from '../../components/Screen';
import { TopBar } from '../../components/TopBar';
import { useApp } from '../../context/AppContext';
import { listProjects } from '../../storage/db';
import type { Project } from '../../types';
import { colors } from '../../theme/colors';

export function ProjectsScreen() {
  const { setScreen, openProject } = useApp();
  const [projects, setProjects] = useState<Project[]>([]);

  const refresh = useCallback(async () => {
    setProjects(await listProjects());
  }, []);

  React.useEffect(() => {
    refresh();
  }, [refresh]);

  return (
    <Screen>
      <TopBar title="Projects" onBack={() => setScreen('dashboard')} right={<AppButton title="New" onPress={() => setScreen('create-project')} />} />
      <Text style={styles.copy}>Tap any project to view details, notes, and sync status.</Text>
      <View style={styles.list}>
        {projects.map((project) => (
          <Pressable key={project.projectUuid} onPress={() => openProject(project)} style={({ pressed }) => [styles.item, pressed && styles.pressed]}>
            <View style={styles.icon}><Text style={styles.iconText}>{project.name.slice(0, 1).toUpperCase()}</Text></View>
            <View style={styles.itemBody}>
              <Text style={styles.name}>{project.name}</Text>
              <Text style={styles.meta}>{project.location || 'No location'} • {project.progress}% • {project.syncStatus}</Text>
            </View>
            <Text style={styles.chevron}>›</Text>
          </Pressable>
        ))}
        {projects.length === 0 ? <Text style={styles.empty}>No projects yet. Create your first mobile project.</Text> : null}
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  copy: { color: colors.slate600, fontSize: 15, lineHeight: 22, marginBottom: 18 },
  list: { gap: 12 },
  item: { flexDirection: 'row', alignItems: 'center', backgroundColor: colors.white, borderRadius: 20, padding: 14, borderWidth: 1, borderColor: colors.slate200 },
  pressed: { opacity: 0.8 },
  icon: { width: 44, height: 44, borderRadius: 15, backgroundColor: colors.blueSoft, alignItems: 'center', justifyContent: 'center' },
  iconText: { color: colors.blueDark, fontWeight: '900', fontSize: 18 },
  itemBody: { flex: 1, marginLeft: 12 },
  name: { color: colors.slate950, fontWeight: '900', fontSize: 16 },
  meta: { color: colors.slate500, fontSize: 12, marginTop: 4 },
  chevron: { color: colors.slate500, fontSize: 30 },
  empty: { color: colors.slate500, textAlign: 'center', padding: 30, lineHeight: 20 }
});
