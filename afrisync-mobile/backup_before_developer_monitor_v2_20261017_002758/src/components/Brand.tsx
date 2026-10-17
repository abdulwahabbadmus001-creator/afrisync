import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { colors } from '../theme/colors';

export function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <View style={styles.row}>
      <View style={styles.mark}>
        <Text style={styles.markText}>A</Text>
      </View>
      {!compact && (
        <View>
          <Text style={styles.name}>AfriSync</Text>
          <Text style={styles.tagline}>Build together. Sync anywhere.</Text>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10
  },
  mark: {
    width: 44,
    height: 44,
    borderRadius: 16,
    backgroundColor: colors.slate950,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 2,
    borderColor: colors.emerald
  },
  markText: {
    color: colors.white,
    fontWeight: '900',
    fontSize: 22
  },
  name: {
    color: colors.slate950,
    fontWeight: '900',
    fontSize: 22,
    letterSpacing: -0.6
  },
  tagline: {
    color: colors.slate500,
    fontSize: 12,
    marginTop: 2
  }
});
