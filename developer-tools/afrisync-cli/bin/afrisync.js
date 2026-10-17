#!/usr/bin/env node
'use strict';

const fs = require('fs');
const path = require('path');
const os = require('os');
const crypto = require('crypto');
const readline = require('readline');
const { spawn, spawnSync } = require('child_process');

const VERSION = '0.1.0';
const HOME_DIR = path.join(os.homedir(), '.afrisync');
const CREDENTIALS_FILE = path.join(HOME_DIR, 'credentials.json');
const PROJECT_DIR = '.afrisync';
const PROJECT_CONFIG = path.join(PROJECT_DIR, 'config.json');
const QUEUE_FILE = path.join(PROJECT_DIR, 'queue.jsonl');

function die(message, code = 1) {
  console.error(`\nAfriSync: ${message}`);
  process.exit(code);
}

function info(message) { console.log(`AfriSync: ${message}`); }
function ok(message) { console.log(`AfriSync ✓ ${message}`); }

function ensureDir(dir) { fs.mkdirSync(dir, { recursive: true }); }
function readJson(file, fallback = null) {
  try { return JSON.parse(fs.readFileSync(file, 'utf8')); } catch { return fallback; }
}
function writeJson(file, value) {
  ensureDir(path.dirname(file));
  fs.writeFileSync(file, JSON.stringify(value, null, 2) + '\n', 'utf8');
}
function normalizeApiUrl(value) { return String(value || '').trim().replace(/\/+$/, ''); }
function nowIso() { return new Date().toISOString(); }
function eventId() { return `evt_${crypto.randomUUID().replace(/-/g, '')}`; }

function parseOption(args, name) {
  const index = args.indexOf(name);
  if (index >= 0 && index + 1 < args.length) return args[index + 1];
  const prefix = `${name}=`;
  const found = args.find((arg) => arg.startsWith(prefix));
  return found ? found.slice(prefix.length) : null;
}

function runGit(args, cwd = process.cwd()) {
  const result = spawnSync('git', args, { cwd, encoding: 'utf8', windowsHide: true });
  if (result.status !== 0) return '';
  return String(result.stdout || '').trim();
}

function detectProject(cwd = process.cwd()) {
  const packageJson = readJson(path.join(cwd, 'package.json'), {});
  const deps = { ...(packageJson.dependencies || {}), ...(packageJson.devDependencies || {}) };
  let framework = 'node';
  if (deps.expo) framework = 'expo';
  else if (deps.next) framework = 'nextjs';
  else if (deps['react-native']) framework = 'react-native';
  else if (deps.vite) framework = 'vite';
  else if (deps.react) framework = 'react';

  const language = fs.existsSync(path.join(cwd, 'tsconfig.json')) ? 'typescript' : 'javascript';
  const repo = runGit(['remote', 'get-url', 'origin'], cwd) || null;
  const branch = runGit(['branch', '--show-current'], cwd) || null;
  const commit = runGit(['rev-parse', 'HEAD'], cwd) || null;
  const dirtyFiles = runGit(['status', '--porcelain'], cwd).split(/\r?\n/).filter(Boolean).length;
  const name = packageJson.name || path.basename(cwd);

  return {
    name,
    framework,
    runtime: `node ${process.version}`,
    language,
    repositoryUrl: repo,
    defaultBranch: branch,
    currentCommit: commit,
    dirtyFiles,
    packageManager: fs.existsSync(path.join(cwd, 'pnpm-lock.yaml')) ? 'pnpm'
      : fs.existsSync(path.join(cwd, 'yarn.lock')) ? 'yarn'
      : 'npm'
  };
}

function readCredentials() {
  const value = readJson(CREDENTIALS_FILE);
  if (!value?.apiKey || !value?.apiUrl) {
    die('You are not logged in. Run: afrisync login --api http://YOUR-IP:8000');
  }
  return value;
}

function readProjectConfig(cwd = process.cwd()) { return readJson(path.join(cwd, PROJECT_CONFIG)); }

async function apiRequest(apiUrl, route, options = {}) {
  const url = `${normalizeApiUrl(apiUrl)}${route.startsWith('/') ? route : `/${route}`}`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), options.timeoutMs || 12000);
  try {
    const response = await fetch(url, {
      method: options.method || 'GET',
      signal: controller.signal,
      headers: {
        Accept: 'application/json',
        ...(options.body !== undefined ? { 'Content-Type': 'application/json' } : {}),
        ...(options.token ? { Authorization: `Bearer ${options.token}` } : {}),
        ...(options.headers || {})
      },
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined
    });
    const text = await response.text();
    let payload = null;
    try { payload = text ? JSON.parse(text) : null; } catch { payload = { message: text }; }
    if (!response.ok) {
      const detail = payload?.detail ?? payload?.message ?? `HTTP ${response.status}`;
      const error = new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
      error.status = response.status;
      throw error;
    }
    return payload;
  } finally {
    clearTimeout(timer);
  }
}

function ask(question) {
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  return new Promise((resolve) => rl.question(question, (answer) => { rl.close(); resolve(answer.trim()); }));
}

async function login(args) {
  const apiUrl = normalizeApiUrl(parseOption(args, '--api') || process.env.AFRISYNC_API_URL || '');
  if (!apiUrl) die('Provide your backend URL, for example: afrisync login --api http://192.168.1.7:8000');

  info(`Testing ${apiUrl} ...`);
  await apiRequest(apiUrl, '/v1/developer/health');
  ok('Developer API is online.');

  const identifier = parseOption(args, '--user') || await ask('Username or email: ');
  const password = process.env.AFRISYNC_PASSWORD || await ask('Password (visible in this local v1): ');
  if (!identifier || !password) die('Username/email and password are required.');

  const session = await apiRequest(apiUrl, '/login', {
    method: 'POST',
    body: { username: identifier, password }
  });
  if (!session?.sync_token) die('Login succeeded but no sync token was returned.');

  const key = await apiRequest(apiUrl, '/v1/developer/api-keys', {
    method: 'POST',
    token: session.sync_token,
    body: { name: `CLI ${os.hostname()}` }
  });
  if (!key?.api_key) die('AfriSync did not return a developer API key.');

  writeJson(CREDENTIALS_FILE, {
    apiUrl,
    apiKey: key.api_key,
    keyId: key.key_id,
    username: session.username || identifier,
    createdAt: nowIso()
  });
  try { fs.chmodSync(CREDENTIALS_FILE, 0o600); } catch {}
  ok(`Logged in as ${session.username || identifier}. Developer API key stored locally.`);
  console.log(`Credentials: ${CREDENTIALS_FILE}`);
}

function ensureGitignore(cwd) {
  const file = path.join(cwd, '.gitignore');
  let content = '';
  try { content = fs.readFileSync(file, 'utf8'); } catch {}
  const line = '.afrisync/';
  if (!content.split(/\r?\n/).includes(line)) {
    if (content && !content.endsWith('\n')) content += '\n';
    content += `${line}\n`;
    fs.writeFileSync(file, content, 'utf8');
  }
}

async function initProject(args = [], quiet = false) {
  const creds = readCredentials();
  const cwd = process.cwd();
  ensureDir(path.join(cwd, PROJECT_DIR));
  ensureGitignore(cwd);

  let config = readProjectConfig(cwd);
  const detected = detectProject(cwd);
  const clientProjectId = config?.clientProjectId || `local_${crypto.randomUUID().replace(/-/g, '')}`;

  const registered = await apiRequest(creds.apiUrl, '/v1/projects/register', {
    method: 'POST',
    token: creds.apiKey,
    body: {
      name: detected.name,
      framework: detected.framework,
      runtime: detected.runtime,
      language: detected.language,
      repository_url: detected.repositoryUrl,
      default_branch: detected.defaultBranch,
      client_project_id: clientProjectId,
      metadata: {
        package_manager: detected.packageManager,
        initialized_from: os.hostname()
      }
    }
  });

  config = {
    version: 1,
    projectId: registered.project_id,
    clientProjectId,
    name: detected.name,
    apiUrl: creds.apiUrl,
    initializedAt: config?.initializedAt || nowIso()
  };
  writeJson(path.join(cwd, PROJECT_CONFIG), config);

  await sendOrQueue({
    project_id: config.projectId,
    event: 'project.initialized',
    timestamp: nowIso(),
    source: 'cli',
    metadata: detected
  }, cwd, true);

  if (!quiet) {
    ok(`${registered.created ? 'Registered' : 'Connected'} project "${detected.name}".`);
    console.log(`Project ID: ${config.projectId}`);
    console.log(`Local config: ${path.join(cwd, PROJECT_CONFIG)}`);
  }
  return config;
}

function queueEvent(event, cwd = process.cwd()) {
  const file = path.join(cwd, QUEUE_FILE);
  ensureDir(path.dirname(file));
  fs.appendFileSync(file, JSON.stringify(event) + '\n', 'utf8');
}

function readQueue(cwd = process.cwd()) {
  const file = path.join(cwd, QUEUE_FILE);
  try {
    return fs.readFileSync(file, 'utf8').split(/\r?\n/).filter(Boolean).map((line) => JSON.parse(line));
  } catch { return []; }
}

function writeQueue(events, cwd = process.cwd()) {
  const file = path.join(cwd, QUEUE_FILE);
  ensureDir(path.dirname(file));
  fs.writeFileSync(file, events.map((item) => JSON.stringify(item)).join('\n') + (events.length ? '\n' : ''), 'utf8');
}

async function sendOrQueue(event, cwd = process.cwd(), silent = false) {
  const creds = readCredentials();
  const normalized = {
    event_id: event.event_id || eventId(),
    project_id: event.project_id,
    event: event.event,
    timestamp: event.timestamp || nowIso(),
    source: event.source || 'cli',
    metadata: event.metadata || {}
  };
  try {
    await apiRequest(creds.apiUrl, '/v1/events', {
      method: 'POST', token: creds.apiKey, body: normalized, timeoutMs: 7000
    });
    if (!silent) ok(`Synced event: ${normalized.event}`);
    return true;
  } catch (error) {
    if (error?.status === 401 || error?.status === 403) throw error;
    queueEvent(normalized, cwd);
    if (!silent) info(`Offline/unreachable: queued ${normalized.event} locally.`);
    return false;
  }
}

async function flushQueue(cwd = process.cwd(), quiet = false) {
  const creds = readCredentials();
  const events = readQueue(cwd);
  if (!events.length) {
    if (!quiet) ok('No pending offline events.');
    return 0;
  }
  try {
    await apiRequest(creds.apiUrl, '/v1/events/batch', {
      method: 'POST', token: creds.apiKey, body: { events }, timeoutMs: 10000
    });
    writeQueue([], cwd);
    if (!quiet) ok(`Synced ${events.length} queued event(s).`);
    return events.length;
  } catch (error) {
    if (!quiet) info(`Queue remains local (${events.length} event(s)): ${error.message}`);
    return 0;
  }
}

async function ensureProject() {
  let config = readProjectConfig();
  if (!config?.projectId) config = await initProject([], true);
  return config;
}

function quoteShellArg(value) {
  const text = String(value);
  if (/^[A-Za-z0-9_./:\\=-]+$/.test(text)) return text;
  return `"${text.replace(/"/g, '\\"')}"`;
}

async function runCommand(args) {
  const separator = args.indexOf('--');
  const commandArgs = separator >= 0 ? args.slice(separator + 1) : args;
  if (!commandArgs.length) die('Usage: afrisync run -- <your normal development command>');

  const config = await ensureProject();
  await flushQueue(process.cwd(), true);
  const before = detectProject();

  await sendOrQueue({
    project_id: config.projectId,
    event: 'development.session.started',
    metadata: {
      command: commandArgs.join(' '),
      branch: before.defaultBranch,
      commit: before.currentCommit,
      dirty_files: before.dirtyFiles,
      framework: before.framework,
      language: before.language
    }
  }, process.cwd(), true);

  console.log(`\nAfriSync tracking: ${commandArgs.join(' ')}`);
  console.log(`Project: ${config.name} (${config.projectId})\n`);
  const startedAt = Date.now();
  const command = commandArgs.map(quoteShellArg).join(' ');
  const child = spawn(command, { cwd: process.cwd(), stdio: 'inherit', shell: true });

  const finish = async (code, signal) => {
    const after = detectProject();
    const durationSeconds = Math.round((Date.now() - startedAt) / 1000);
    try {
      await sendOrQueue({
        project_id: config.projectId,
        event: 'development.session.ended',
        metadata: {
          command: commandArgs.join(' '),
          exit_code: code,
          signal: signal || null,
          duration_seconds: durationSeconds,
          branch: after.defaultBranch,
          commit_before: before.currentCommit,
          commit_after: after.currentCommit,
          commit_changed: before.currentCommit !== after.currentCommit,
          dirty_files_before: before.dirtyFiles,
          dirty_files_after: after.dirtyFiles
        }
      }, process.cwd(), true);
      await flushQueue(process.cwd(), true);
    } catch (error) {
      info(`Session ended; event remained local: ${error.message}`);
    }
    process.exit(typeof code === 'number' ? code : 0);
  };
  child.on('exit', finish);
  child.on('error', (error) => die(`Could not start command: ${error.message}`));
}

async function track(args) {
  const config = await ensureProject();
  const eventName = args[0];
  if (!eventName) die('Usage: afrisync track <event.name> [--data JSON]');
  let metadata = {};
  const raw = parseOption(args, '--data');
  if (raw) {
    try { metadata = JSON.parse(raw); } catch { die('--data must be valid JSON.'); }
  }
  await sendOrQueue({ project_id: config.projectId, event: eventName, metadata });
}

async function progress(args) {
  const config = await ensureProject();
  const percent = Number(args[0]);
  if (!Number.isFinite(percent) || percent < 0 || percent > 100) die('Usage: afrisync progress <0-100> [--stage NAME] [--status STATUS]');
  await sendOrQueue({
    project_id: config.projectId,
    event: 'project.progress',
    metadata: {
      percent,
      stage: parseOption(args, '--stage'),
      status: parseOption(args, '--status')
    }
  });
}

async function status() {
  const creds = readCredentials();
  const config = readProjectConfig();
  const queued = readQueue().length;
  console.log('\nAfriSync Developer CLI');
  console.log(`Version: ${VERSION}`);
  console.log(`Account: ${creds.username || 'connected'}`);
  console.log(`API: ${creds.apiUrl}`);
  console.log(`Project: ${config?.name || 'not initialized'}`);
  console.log(`Project ID: ${config?.projectId || '-'}`);
  console.log(`Offline queue: ${queued} pending event(s)`);
  console.log('');
}

function help() {
  console.log(`
AfriSync Developer CLI v${VERSION}

One-time account connection:
  afrisync login --api http://YOUR-LAPTOP-IP:8000

One-time per project:
  cd C:\\path\\to\\your-project
  afrisync init

Normal development:
  afrisync run -- npx expo start
  afrisync run -- npm run dev
  afrisync run -- python app.py

Manual project signals (optional):
  afrisync progress 60 --stage authentication --status active
  afrisync track feature.completed --data "{\\"feature\\":\\"Login\\"}"

Utilities:
  afrisync status
  afrisync sync
  afrisync logout
`);
}

async function main() {
  const [, , command, ...args] = process.argv;
  try {
    switch (command) {
      case 'login': return await login(args);
      case 'logout':
        try { fs.unlinkSync(CREDENTIALS_FILE); } catch {}
        return ok('Local AfriSync credentials removed.');
      case 'init': return await initProject(args);
      case 'run': return await runCommand(args);
      case 'track': return await track(args);
      case 'progress': return await progress(args);
      case 'status': return await status();
      case 'sync': return await flushQueue();
      case '--version': case '-v': return console.log(VERSION);
      case '--help': case '-h': case undefined: return help();
      default: die(`Unknown command: ${command}. Run: afrisync --help`);
    }
  } catch (error) {
    die(error?.message || String(error));
  }
}

main();
