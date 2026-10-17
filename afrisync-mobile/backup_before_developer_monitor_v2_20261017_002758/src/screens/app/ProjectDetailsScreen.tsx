import React, { useCallback, useState } from 'react';
import { Alert, StyleSheet, Text, View } from 'react-native';
import { AppButton } from '../../components/AppButton';
import { AppInput } from '../../components/AppInput';
import { Card, Screen } from '../../components/Screen';
import { TopBar } from '../../components/TopBar';
import { useApp } from '../../context/AppContext';
import { createNote, listProjectNotes } from '../../storage/db';
import type { Note } from '../../types';
import { colors } from '../../theme/colors';

export function ProjectDetailsScreen() {
  const { selectedProject, setScreen } = useApp();
  const [notes, setNotes] = useState<Note[]>([]);
  const [note, setNote] = useState('');

  const refresh = useCallback(async () => {
    if (!selectedProject) return;
    setNotes(await listProjectNotes(selectedProject.projectUuid));
  }, [selectedProject]);

  React.useEffect(() => {
    refresh();
  }, [refresh]);

  async function saveNote() {
    if (!selectedProject || !note.trim()) {
      Alert.alert('Note required', 'Write a note before saving.');
      return;
    }
    await createNote(selectedProject.projectUuid, note);
    setNote('');
    await refresh();
  }

  if (!selectedProject) {
    return (
      <Screen>
        <TopBar title="Project" onBack={() => setScreen('projects')} />
        <Text>No selected project.</Text>
      </Screen>
    );
  }

  return (
    <Screen>
      <TopBar title="Project details" onBack={() => setScreen('projects')} />
      <Card>
        <Text style={styles.name}>{selectedProject.name}</Text>
        <Text style={styles.meta}>{selectedProject.location || 'No location'} • {selectedProject.progress}% complete</Text>
        <Text style={styles.status}>Status: {selectedProject.syncStatus}</Text>
        {selectedProject.description ? <Text style={styles.description}>{selectedProject.description}</Text> : null}
      </Card>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Notes</Text>
        <Card>
          <View style={styles.form}>
            <AppInput label="New note" value={note} onChangeText={setNote} placeholder="Write a project note..." multiline />
            <AppButton title="Save note offline" onPress={saveNote} />
          </View>
        </Card>
        <View style={styles.notes}>
          {notes.map((item) => (
            <View key={item.noteUuid} style={styles.noteCard}>
              <Text style={styles.noteText}>{item.content}</Text>
              <Text style={styles.noteMeta}>{item.syncStatus} • {new Date(item.createdAt).toLocaleString()}</Text>
            </View>
          ))}
        </View>
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  name: { color: colors.slate950, fontSize: 26, fontWeight: '900' },
  meta: { color: colors.slate600, marginTop: 6, fontSize: 14 },
  status: { color: colors.blue, marginTop: 12, fontWeight: '900' },
  description: { color: colors.slate700, marginTop: 12, lineHeight: 21 },
  section: { marginTop: 22 },
  sectionTitle: { color: colors.slate950, fontSize: 20, fontWeight: '900', marginBottom: 12 },
  form: { gap: 12 },
  notes: { gap: 10, marginTop: 12 },
  noteCard: { backgroundColor: colors.white, borderRadius: 18, padding: 14, borderWidth: 1, borderColor: colors.slate200 },
  noteText: { color: colors.slate900, lineHeight: 21 },
  noteMeta: { color: colors.slate500, fontSize: 12, marginTop: 8 }
});
