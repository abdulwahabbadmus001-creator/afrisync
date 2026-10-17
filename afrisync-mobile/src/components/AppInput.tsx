import React, { useState } from 'react';
import { StyleSheet, Text, TextInput, TextInputProps, View } from 'react-native';
import { useTheme } from '../theme/theme';

export function AppInput({ label, error, helper, ...props }: TextInputProps & { label: string; error?: string; helper?: string }) {
  const { palette } = useTheme();
  const [focused, setFocused] = useState(false);
  const originalFocus = props.onFocus;
  const originalBlur = props.onBlur;

  return (
    <View style={styles.wrap}>
      <Text style={[styles.label, { color: palette.textMuted }]}>{label}</Text>
      <TextInput
        {...props}
        placeholderTextColor={palette.textSubtle}
        onFocus={event => { setFocused(true); originalFocus?.(event); }}
        onBlur={event => { setFocused(false); originalBlur?.(event); }}
        style={[
          styles.input,
          { backgroundColor: palette.input, color: palette.text, borderColor: error ? palette.red : focused ? palette.primary : palette.border },
          props.multiline && styles.multiline
        ]}
      />
      {error ? <Text style={[styles.meta, { color: palette.red }]}>{error}</Text> : helper ? <Text style={[styles.meta, { color: palette.textSubtle }]}>{helper}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { gap: 7 },
  label: { fontWeight: '800', fontSize: 12.5, letterSpacing: 0.2 },
  input: { minHeight: 52, borderRadius: 13, borderWidth: 1, paddingHorizontal: 15, fontSize: 15 },
  multiline: { minHeight: 100, paddingTop: 14, textAlignVertical: 'top' },
  meta: { fontSize: 11.5, lineHeight: 16 }
});
