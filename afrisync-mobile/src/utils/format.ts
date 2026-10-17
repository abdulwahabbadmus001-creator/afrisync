import type { DeveloperEvent } from '../types';

export function formatDateTime(value?: string | null): string {
  if (!value) return 'No activity yet';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

export function formatRelative(value?: string | null): string {
  if (!value) return 'No activity yet';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const seconds = Math.max(0, Math.floor((Date.now() - date.getTime()) / 1000));
  if (seconds < 60) return 'Just now';
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return date.toLocaleDateString();
}

export function eventLabel(type: string): string {
  const map: Record<string, string> = {
    'project.initialized': 'Project connected',
    'development.session.started': 'Development session started',
    'development.session.ended': 'Development session ended',
    'project.progress': 'Project progress updated',
    'feature.completed': 'Feature completed',
    'build.failed': 'Build failed',
    'build.succeeded': 'Build succeeded',
    'test.failed': 'Tests failed',
    'test.passed': 'Tests passed'
  };
  if (map[type]) return map[type];
  return type.split('.').map(part => part.charAt(0).toUpperCase() + part.slice(1)).join(' ');
}

export function eventTone(type: string): 'good' | 'warn' | 'bad' | 'info' | 'neutral' {
  const lower = type.toLowerCase();
  if (lower.includes('failed') || lower.includes('error') || lower.includes('conflict')) return 'bad';
  if (lower.includes('warning')) return 'warn';
  if (lower.includes('ended') || lower.includes('completed') || lower.includes('succeeded') || lower.includes('passed') || lower.includes('initialized')) return 'good';
  if (lower.includes('started') || lower.includes('progress')) return 'info';
  return 'neutral';
}

export function isActiveSession(events: DeveloperEvent[]): boolean {
  const start = events.find(e => e.eventType === 'development.session.started');
  const end = events.find(e => e.eventType === 'development.session.ended');
  if (!start) return false;
  if (!end) return true;
  return new Date(start.occurredAt).getTime() > new Date(end.occurredAt).getTime();
}
