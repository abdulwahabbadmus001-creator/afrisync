import React from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, ViewStyle } from 'react-native';
import { useTheme } from '../theme/theme';

export function AppButton({
  title,
  onPress,
  variant = 'primary',
  loading = false,
  disabled = false,
  style,
  compact = false
}: {
  title: string;
  onPress: () => void;
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  loading?: boolean;
  disabled?: boolean;
  style?: ViewStyle;
  compact?: boolean;
}) {
  const { palette } = useTheme();
  const backgroundColor = variant === 'primary' ? palette.primary : variant === 'secondary' ? palette.surfaceAlt : variant === 'danger' ? palette.red : 'transparent';
  const borderColor = variant === 'secondary' ? palette.border : 'transparent';
  const textColor = variant === 'primary' || variant === 'danger' ? palette.white : variant === 'secondary' ? palette.text : palette.primary;

  return (
    <Pressable
      onPress={onPress}
      disabled={loading || disabled}
      style={({ pressed }) => [
        styles.base,
        compact && styles.compact,
        { backgroundColor, borderColor, opacity: pressed ? 0.82 : loading || disabled ? 0.5 : 1 },
        style
      ]}
    >
      {loading ? <ActivityIndicator color={textColor} /> : <Text style={[styles.text, { color: textColor }]}>{title}</Text>}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  base: { minHeight: 52, borderRadius: 14, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 18, borderWidth: 1 },
  compact: { minHeight: 40, borderRadius: 12, paddingHorizontal: 14 },
  text: { fontWeight: '800', fontSize: 15, letterSpacing: 0.1 }
});
