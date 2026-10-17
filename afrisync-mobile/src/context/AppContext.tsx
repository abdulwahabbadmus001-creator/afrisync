import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';
import { getApiBaseUrl } from '../config/env';
import { clearSession, getSavedSession, saveSession } from '../storage/session';
import type { DeveloperProject, RootScreen, UserSession } from '../types';

type AppContextValue = {
  booting: boolean;
  session: UserSession | null;
  screen: RootScreen;
  selectedProject: DeveloperProject | null;
  verificationIdentifier: string;
  setVerificationIdentifier: (value: string) => void;
  setScreen: (screen: RootScreen) => void;
  openProject: (project: DeveloperProject) => void;
  signIn: (session: UserSession) => Promise<void>;
  signOut: () => Promise<void>;
};

const AppContext = createContext<AppContextValue | undefined>(undefined);

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [booting, setBooting] = useState(true);
  const [session, setSession] = useState<UserSession | null>(null);
  const [screen, setScreen] = useState<RootScreen>('backend-setup');
  const [selectedProject, setSelectedProject] = useState<DeveloperProject | null>(null);
  const [verificationIdentifier, setVerificationIdentifier] = useState('');

  useEffect(() => {
    let mounted = true;
    (async () => {
      const [saved, apiUrl] = await Promise.all([getSavedSession(), getApiBaseUrl()]);
      if (!mounted) return;
      if (saved?.syncToken) {
        setSession(saved);
        setScreen(apiUrl ? 'dashboard' : 'backend-setup');
      } else {
        setScreen(apiUrl ? 'login' : 'backend-setup');
      }
      setBooting(false);
    })();
    return () => { mounted = false; };
  }, []);

  const value = useMemo<AppContextValue>(() => ({
    booting,
    session,
    screen,
    selectedProject,
    verificationIdentifier,
    setVerificationIdentifier,
    setScreen,
    openProject(project) {
      setSelectedProject(project);
      setScreen('project-details');
    },
    async signIn(next) {
      await saveSession(next);
      setSession(next);
      setScreen('dashboard');
    },
    async signOut() {
      await clearSession();
      setSession(null);
      setSelectedProject(null);
      setScreen('login');
    }
  }), [booting, session, screen, selectedProject, verificationIdentifier]);

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp() {
  const value = useContext(AppContext);
  if (!value) throw new Error('useApp must be used inside AppProvider');
  return value;
}
