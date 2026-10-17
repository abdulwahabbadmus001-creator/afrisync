import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';
import type { Project, RootScreen, UserSession } from '../types';
import { initDatabase } from '../storage/db';
import { clearSession, getSavedSession, saveSession } from '../storage/session';

type AppContextValue = {
  booting: boolean;
  session: UserSession | null;
  screen: RootScreen;
  selectedProject: Project | null;
  verificationEmail: string;
  setVerificationEmail: (email: string) => void;
  setScreen: (screen: RootScreen) => void;
  openProject: (project: Project) => void;
  signIn: (session: UserSession) => Promise<void>;
  signOut: () => Promise<void>;
};

const AppContext = createContext<AppContextValue | undefined>(undefined);

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [booting, setBooting] = useState(true);
  const [session, setSession] = useState<UserSession | null>(null);
  const [screen, setScreen] = useState<RootScreen>('login');
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [verificationEmail, setVerificationEmail] = useState('');

  useEffect(() => {
    let mounted = true;
    async function boot() {
      await initDatabase();
      const saved = await getSavedSession();
      if (!mounted) return;
      if (saved?.syncToken) {
        setSession(saved);
        setScreen('dashboard');
      }
      setBooting(false);
    }
    boot();
    return () => {
      mounted = false;
    };
  }, []);

  const value = useMemo<AppContextValue>(() => ({
    booting,
    session,
    screen,
    selectedProject,
    verificationEmail,
    setVerificationEmail,
    setScreen,
    openProject(project: Project) {
      setSelectedProject(project);
      setScreen('project-details');
    },
    async signIn(nextSession: UserSession) {
      await saveSession(nextSession);
      setSession(nextSession);
      setScreen('dashboard');
    },
    async signOut() {
      await clearSession();
      setSession(null);
      setSelectedProject(null);
      setScreen('login');
    }
  }), [booting, session, screen, selectedProject, verificationEmail]);

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp() {
  const context = useContext(AppContext);
  if (!context) throw new Error('useApp must be used inside AppProvider');
  return context;
}
