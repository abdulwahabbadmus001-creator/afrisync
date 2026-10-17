<div align="center">
  <img src="assets/afrisync_connected_africa_logo.png" alt="AfriSync logo" width="220" />

# AfriSync

### Build together. Stay in sync — even when connectivity does not.

An open-source, offline-first synchronization platform built around a practical question: **how can developers and teams keep useful work moving when internet access is intermittent, expensive, or unreliable?**

[![Python](https://img.shields.io/badge/Python-3.x-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-API-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![SQLite](https://img.shields.io/badge/SQLite-Offline%20Storage-003B57?logo=sqlite&logoColor=white)](https://sqlite.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Migration%20Ready-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![React Native](https://img.shields.io/badge/React%20Native-Mobile-61DAFB?logo=react&logoColor=111827)](https://reactnative.dev/)
[![Expo](https://img.shields.io/badge/Expo-Mobile%20Tooling-000020?logo=expo&logoColor=white)](https://expo.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-Mobile-3178C6?logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Git](https://img.shields.io/badge/Git-Version%20Control-F05032?logo=git&logoColor=white)](https://git-scm.com/)
[![GitHub](https://img.shields.io/badge/GitHub-Open%20Source-181717?logo=github&logoColor=white)](https://github.com/)
[![Docker](https://img.shields.io/badge/Docker-Deployment-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)

</div>

## Why AfriSync exists

AfriSync started as a learning and engineering experiment around a problem that is common across many African digital environments: software is often designed as though continuous connectivity is guaranteed. In practice, developers, small teams, students, field workers, businesses, and communities may work through unstable networks, expensive data, power interruptions, or long periods without reliable access.

The project therefore began with a simple principle:

> **Local work should remain useful when the network disappears, and synchronization should happen safely when connectivity returns.**

AfriSync is not an attempt to claim that Africa has no internet or no cloud infrastructure. It is a developer-oriented response to uneven connectivity conditions and to the broader need for resilient software that treats offline operation as a first-class state rather than an exceptional failure.

## Vision

To make resilient, offline-capable software infrastructure easier to build, understand, and extend — especially for developers working in connectivity-constrained environments across Africa and other parts of the world.

## Mission

AfriSync aims to:

- keep application data usable locally when a network is unavailable;
- synchronize local and remote state when connectivity returns;
- make sync status, conflicts, failures, retries, and activity understandable to developers;
- support secure multi-device and team workflows;
- provide an open-source foundation that other developers can inspect, improve, and adapt;
- grow from a Python/FastAPI synchronization experiment into a polished mobile developer platform.

## The journey: how the project evolved

### 1. Local-first Python prototype

The first AfriSync implementation was a Python application using local SQLite storage. Records could be created locally and marked with synchronization states such as `PENDING`, `SYNCED`, `CONFLICT`, or `ERROR`.

The first goal was not UI polish. It was to prove the central behavior:

```text
create locally → keep working offline → detect connectivity → push changes → mark synchronized
```

This established the local-first data model and the sync queue.

### 2. FastAPI remote synchronization API

The project then moved from a local demonstration to a client/server model. A FastAPI remote server became the synchronization target, with Pydantic models and HTTP API calls between local clients and the remote service.

This introduced:

- remote project and record APIs;
- push and pull synchronization;
- network-aware retry behavior;
- authenticated synchronization tokens;
- health checks and server status;
- explicit server-side persistence.

The key architectural shift was from "write directly to one database" to **"local database first, API synchronization second."**

### 3. Multi-device simulation

AfriSync then introduced separate simulated devices with independent SQLite databases. Device A and Device B could both work with local data and exchange changes through the remote FastAPI server.

This stage was important because synchronization only becomes meaningful when multiple independent copies of state can diverge.

### 4. Notes, attachments, tombstones and versioning

The synchronization model expanded beyond projects to include notes and file attachments. Deletion synchronization uses tombstone-style state instead of assuming that removing a local row is enough. Version information and conflict handling were added so that incompatible edits can be surfaced instead of silently overwritten.

### 5. Activity, notifications and sync history

The application grew developer-facing observability features:

- synchronization history;
- activity events;
- notifications;
- error states;
- conflict-resolution surfaces;
- latest synchronization timestamps.

The objective is that sync should not be a hidden background mystery. Developers should be able to see what happened.

### 6. Team collaboration and permissions

AfriSync expanded into collaborative use with team invitations and project roles such as owner, editor, and viewer. Permission checks were introduced so synchronization and project operations can respect collaboration boundaries.

### 7. Authentication and security

The project added account and security workflows including:

- local secure sessions;
- CSRF protection for browser-facing flows;
- bearer tokens for synchronization APIs;
- password reset;
- email verification;
- Google authentication support for the web workflow;
- developer API-key metadata;
- local secret/config separation through `.gitignore` and environment configuration.

### 8. Admin and developer monitoring interfaces

A separate administration surface was created for system monitoring, user/project visibility, health information, and operational actions. The original browser dashboard was also progressively redesigned to improve project, activity, notification, and sync visibility.

### 9. PostgreSQL and deployment preparation

SQLite remains valuable for local/offline storage. For remote/hosted deployment, the repository also contains PostgreSQL migration preparation and database abstraction work. Deployment assets and experiments include Uvicorn launchers, Docker configuration, environment-based settings, health checks, and backup tooling.

PostgreSQL support should be understood as part of the server deployment path; SQLite remains central to the offline-first client design.

### 10. AfriSync Mobile

The current direction is **AfriSync Mobile**, built with Expo, React Native, and TypeScript. The mobile application acts as a developer monitor and synchronization surface for projects registered through AfriSync tooling.

Current mobile work includes:

- authentication and email verification screens;
- developer dashboard;
- connected project monitoring;
- active-session and synchronization metrics;
- project details and development events;
- sync center;
- notifications;
- appearance settings;
- secure local session storage;
- API connection handling;
- production API configuration through build-time environment variables;
- Android APK preparation through EAS Build.

## Architecture

```text
┌──────────────────────────────────────────────┐
│              Developer / User               │
└──────────────────────┬───────────────────────┘
                       │
          ┌────────────┴────────────┐
          │                         │
          ▼                         ▼
┌───────────────────┐      ┌────────────────────┐
│ AfriSync Mobile   │      │ Local/Web Client   │
│ Expo + RN + TS    │      │ Python + SQLite    │
└─────────┬─────────┘      └──────────┬─────────┘
          │ HTTPS / API               │ sync engine
          └────────────┬──────────────┘
                       ▼
              ┌─────────────────┐
              │ FastAPI Server  │
              │ Auth + Sync API │
              └────────┬────────┘
                       │
          ┌────────────┴────────────┐
          ▼                         ▼
┌───────────────────┐      ┌────────────────────┐
│ SQLite            │      │ PostgreSQL path    │
│ local/offline     │      │ hosted migration   │
└───────────────────┘      └────────────────────┘
```

## Synchronization model

At a high level, AfriSync follows this lifecycle:

```text
1. Write to local storage first
2. Mark unsynchronized work as pending
3. Detect whether the remote API is reachable
4. Push local pending changes
5. Pull remote changes
6. Compare versions/state
7. Apply compatible updates
8. Surface conflicts instead of silently discarding edits
9. Record synchronization/activity history
10. Continue working locally if connectivity disappears again
```

This approach keeps offline operation useful while preserving a path back to shared remote state.

## Technology stack

| Layer | Technology | Purpose |
|---|---|---|
| Core/backend | Python | Sync engine, server logic, scripts and tooling |
| API | FastAPI | Remote HTTP API and synchronization endpoints |
| API runtime | Uvicorn | ASGI development/production serving |
| Validation | Pydantic | Request/response data validation |
| Offline database | SQLite | Local-first persistence and simulated device storage |
| Hosted database path | PostgreSQL | Server-side production migration path |
| Mobile | React Native | Native mobile user interface |
| Mobile framework | Expo | Android/iOS tooling, development and builds |
| Mobile language | TypeScript | Typed mobile application code |
| Secure mobile storage | Expo SecureStore | Device-side session/token storage |
| Mobile SQLite | expo-sqlite | Offline structured data persistence |
| Connectivity | NetInfo | Network-state awareness |
| Mobile files | Expo FileSystem | Attachment/file handling |
| Browser UI | HTML/CSS/JavaScript | Earlier local/web dashboard surfaces |
| Version control | Git + GitHub | Open-source development and collaboration |
| Windows tooling | PowerShell | Local launch, test, migration and deployment scripts |
| Packaging experiments | PyInstaller/Tkinter | Desktop launcher work |
| Deployment | Docker + environment configuration | Reproducible server deployment preparation |

## Project structure

The repository is intentionally broader than the mobile client because it records the evolution of AfriSync.

```text
AfriSync/
├── server.py                    # remote FastAPI server
├── local_app.py                 # local application/API
├── admin_app.py                 # administration interface
├── app/
│   ├── database.py
│   ├── project_service.py
│   └── sync_engine.py           # synchronization logic
├── templates/                   # browser dashboard UI
├── assets/                      # AfriSync brand assets
├── afrisync_db.py               # database abstraction / PostgreSQL path
├── background_sync.py
├── pull_sync.py
├── auto_sync.py
├── migration and check scripts
└── afrisync-mobile/             # Expo React Native + TypeScript client
    ├── App.tsx
    ├── app.json
    ├── eas.json
    ├── src/
    │   ├── components/
    │   ├── config/
    │   ├── context/
    │   ├── screens/
    │   ├── services/
    │   ├── storage/
    │   ├── theme/
    │   └── utils/
    └── assets/
```

## Mobile development vs production API connection

During local development, a physical phone cannot use the PC's `localhost`. The Expo app therefore uses the computer's LAN IPv4 address, for example:

```text
http://192.168.1.10:8000
```

This is **development only**.

For an APK or production release, AfriSync uses a build-time environment variable:

```bash
EXPO_PUBLIC_AFRISYNC_API_URL=https://your-production-api.example.com
```

Production builds should use HTTPS. The production mobile UI does not require a user to type or save the API URL; it can test the configured endpoint, but the endpoint itself is fixed by the build.

## Android build path

AfriSync Mobile uses Expo/EAS for Android builds.

```bash
npm install -g eas-cli
eas login
eas build:configure
eas build --platform android --profile preview
```

The `preview` profile generates an installable APK for device testing. A later `production` profile can generate an Android App Bundle for store distribution.

## Why the AfriSync logo looks the way it does

The AfriSync identity combines several ideas in one visual system:

- **Africa** represents the project's origin and the connectivity realities that motivated the work.
- **Database/storage imagery** represents local persistence: data should remain available even before synchronization succeeds.
- **Sync arrows / connected nodes** represent movement between local and remote state and between devices.
- **Code/developer symbolism** reflects the project's developer-first nature rather than positioning AfriSync as only an end-user cloud drive.

The logo is therefore not decorative branding added after the engineering work. It visually describes the project's architecture and purpose.

## Why these colours

AfriSync's core palette uses deep green/emerald, technology blue, amber accents, charcoal, and clean neutral backgrounds.

- **Emerald / green** — resilience, growth, continuity, and an African-rooted identity.
- **Blue** — technology, data, networks, reliability, and synchronization.
- **Amber** — active work, warnings, attention states, and energy.
- **Charcoal** — engineering seriousness and developer-tool sophistication.
- **White / neutral space** — clarity, readability, and a restrained professional interface.

The UI deliberately uses colour semantically: healthy/synced states lean green, active/warning states use amber, and core interactive/data states use blue.

## What AfriSync is becoming

AfriSync is moving toward a developer platform where a developer can register a codebase, work normally, and use AfriSync to monitor synchronization state and development activity across devices and environments.

The longer-term direction includes:

- stronger background/offline synchronization on mobile;
- production HTTPS API deployment;
- Android-first distribution, followed by iOS;
- improved conflict visualization and resolution;
- better attachment synchronization;
- richer team collaboration;
- a more complete CLI/developer workflow;
- production PostgreSQL deployment;
- observability and sync diagnostics;
- community contributions and reusable sync components.

## Open-source philosophy

AfriSync is being developed in the spirit of open-source infrastructure: useful tools improve when other developers can inspect them, challenge assumptions, reproduce problems, and contribute better implementations.

The project welcomes developers interested in:

- offline-first systems;
- distributed synchronization;
- FastAPI and Python backends;
- React Native / Expo;
- SQLite and PostgreSQL;
- conflict resolution;
- mobile UX;
- developer tooling;
- resilient technology for African contexts.

## Security

Never commit local databases, tokens, private keys, `.env` files, email credentials, API secrets, or generated server secrets.

If a secret is ever committed publicly, removing the file from the latest branch is **not enough**. Rotate/revoke the exposed credential because it may remain in Git history, caches, forks, or clones.

See `.gitignore` before committing local work.

## Current status

AfriSync is under active development. The core synchronization concepts have been implemented and tested through local-first storage, remote FastAPI synchronization, multi-device simulation, project/note/attachment synchronization, team permissions, activity history, authentication, and monitoring interfaces. The current milestone is the mobile developer experience and Android packaging.

For setup details, see [`SETUP_AND_RUN.md`](SETUP_AND_RUN.md). For historical mobile planning, see [`MOBILE_APP_CONVERSION_PLAN.md`](MOBILE_APP_CONVERSION_PLAN.md).

## Contributing

Issues, bug reports, architecture discussions, documentation improvements, mobile UX work, and synchronization experiments are welcome. Before submitting sensitive logs or databases, remove credentials, tokens, email addresses, and private user data.

---

<div align="center">

**AfriSync — resilient synchronization for developers working in the real world.**

</div>
