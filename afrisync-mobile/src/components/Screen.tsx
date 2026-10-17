import React from 'react';
import {
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleProp,
  StyleSheet,
  View,
  ViewStyle,
} from 'react-native';
import { useTheme } from '../theme/theme';

export function Screen({
  children,
  padded = true,
  contentStyle,
}: {
  children: React.ReactNode;
  padded?: boolean;
  contentStyle?: StyleProp<ViewStyle>;
}) {
  const { palette } = useTheme();

  return (
    <KeyboardAvoidingView
      behavior={Platform.select({ ios: 'padding', android: undefined })}
      style={[styles.root, { backgroundColor: palette.background }]}
    >
      <ScrollView
        contentContainerStyle={[
          styles.content,
          padded && styles.padded,
          contentStyle,
        ]}
        keyboardShouldPersistTaps="handled"
        showsVerticalScrollIndicator={false}
      >
        {children}
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

export function Card({
  children,
  strong = false,
  style,
}: {
  children: React.ReactNode;
  strong?: boolean;
  style?: StyleProp<ViewStyle>;
}) {
  const { palette } = useTheme();

  return (
    <View
      style={[
        styles.card,
        {
          backgroundColor: strong
            ? palette.surfaceStrong
            : palette.surface,
          borderColor: strong
            ? palette.borderStrong
            : palette.border,
          shadowColor: palette.shadow,
        },
        style,
      ]}
    >
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
  },

  content: {
    flexGrow: 1,
  },

  padded: {
    paddingHorizontal: 18,
    paddingTop: 42,
    paddingBottom: 34,
  },

  card: {
    borderRadius: 20,
    borderWidth: 1,
    padding: 18,
    shadowOpacity: 0.05,
    shadowRadius: 14,
    shadowOffset: {
      width: 0,
      height: 7,
    },
    elevation: 2,
  },
});