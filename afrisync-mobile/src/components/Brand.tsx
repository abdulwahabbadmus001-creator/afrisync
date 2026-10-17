import React from 'react';
import { Image, StyleSheet, View } from 'react-native';

export function Brand({ compact = false, auth = false }: { compact?: boolean; auth?: boolean }) {
  return (
    <View style={styles.wrap}>
      <Image
        source={require('../../assets/afrisync_logo.png')}
        style={compact ? styles.compact : auth ? styles.auth : styles.full}
        resizeMode="contain"
      />
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { alignItems: 'center', justifyContent: 'center', backgroundColor: 'transparent' },
  full: { width: 210, height: 156 },
  auth: { width: 205, height: 154 },
  compact: { width: 88, height: 64 }
});
