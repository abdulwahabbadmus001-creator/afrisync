Do not panic, but treat those files as exposed because the repo is public.

You should remove them from GitHub immediately and keep them only on your laptop.

Best fix for your case

Because this repo was just created, the cleanest method is to rebuild the Git history and force-push only safe files.

Run these commands exactly.

1. Enter your AfriSync folder
cd "C:\Users\user\OneDrive\Desktop\afrisync"
2. Remove Git history from your local folder

This does not delete your project files. It only removes the Git tracking folder.

Remove-Item -Recurse -Force .git
3. Confirm .gitignore contains these lines

Open your .gitignore and make sure these are inside:

.venv/
__pycache__/
*.pyc

server.db
afrisync_device_a.db
afrisync_device_b.db
*.db
*.sqlite
*.sqlite3

server_uploads/
uploads/
uploads_device_a/
uploads_device_b/
backups/

.env
sync_secret.key
*.key

afrisync_email_config.ps1
afrisync_google_config.ps1
afrisync_postgres_config.ps1
afrisync_production_config.ps1

*.log
dist/
build/
*.exe

Save the file.

4. Start Git again
git init
git branch -M main
5. Connect GitHub again
git remote add origin https://github.com/abdulwahabbadmus001-creator/afrisync.git
6. Add files again safely
git add .
7. Check what Git wants to push
git status --short

Carefully check that these are not listed:

server.db
afrisync_email_config.ps1
afrisync_postgres_config.ps1
afrisync_google_config.ps1
.venv
server_uploads
uploads_device_a
uploads_device_b
backups
sync_secret.key

If they are not showing, continue.

8. Commit again
git commit -m "Initial safe open-source release of AfriSync"
9. Force-push the clean version to GitHub
git push -u origin main --force

This will replace the GitHub repo content with the safe version from your laptop.

10. Check GitHub again

Open:

https://github.com/abdulwahabbadmus001-creator/afrisync

Confirm these files are gone:

server.db
afrisync_email_config.ps1
afrisync_postgres_config.ps1
afrisync_google_config.ps1
Very important security step

Since afrisync_email_config.ps1 appeared on GitHub, change/revoke the Gmail App Password you used there.

Also change anything private inside:

afrisync_postgres_config.ps1
afrisync_google_config.ps1
afrisync_production_config.ps1

For server.db, it may contain test users, emails, hashed passwords, projects, notes, or tokens. Removing it is correct. It should never be public.

After the force push, run:

git status

Expected result:

nothing to commit, working tree clean
There is nothing inside the .gitignore file 

Yes, that is the problem. Your .gitignore being empty is why private files entered GitHub.

Do this now.

1. Fill .gitignore automatically

Run this full command inside PowerShell:

cd "C:\Users\user\OneDrive\Desktop\afrisync"

@'
# =========================
# AfriSync Git Ignore Rules
# =========================

# Python environment
.venv/
venv/
env/
__pycache__/
*.pyc
*.pyo
*.pyd
.Python

# Local databases - DO NOT PUSH
server.db
afrisync_device_a.db
afrisync_device_b.db
*.db
*.sqlite
*.sqlite3

# Upload folders - DO NOT PUSH
server_uploads/
uploads/
uploads_device_a/
uploads_device_b/
backups/

# Secret/config files - DO NOT PUSH
.env
*.env
sync_secret.key
*.key

afrisync_email_config.ps1
afrisync_google_config.ps1
afrisync_postgres_config.ps1
afrisync_production_config.ps1

# Logs
*.log
logs/

# Build outputs
dist/
build/
*.exe
*.spec

# OS/editor files
.DS_Store
Thumbs.db
.vscode/
.idea/

# Cache
.pytest_cache/
.mypy_cache/
.ruff_cache/
'@ | Set-Content -Encoding UTF8 .gitignore
2. Confirm it is no longer empty

Run:

Get-Content .gitignore

You should now see many lines inside it.

3. Remove old Git tracking and rebuild safely

Run:

Remove-Item -Recurse -Force .git

Then:

git init
git branch -M main
git remote add origin https://github.com/abdulwahabbadmus001-creator/afrisync.git
4. Add files safely again
git add .

Now check what Git wants to upload:

git status --short

Make sure these files are not showing:

server.db
afrisync_email_config.ps1
afrisync_postgres_config.ps1
afrisync_google_config.ps1
.venv
server_uploads
uploads_device_a
uploads_device_b
backups
sync_secret.key
5. Commit
git commit -m "Initial safe open-source release of AfriSync"
6. Force-push the clean version
git push -u origin main --force
7. Check GitHub

Open your repo and confirm the private files are gone:

https://github.com/abdulwahabbadmus001-creator/afrisync
Important security step

Because afrisync_email_config.ps1 and database files already appeared online, change/revoke those secrets:

Gmail App Password
PostgreSQL password
Google OAuth secret/config if exposed
Any admin/default production passwords

The .gitignore only prevents future uploads. It does not make already-exposed secrets safe again.

NOw, The README.md I don't like how it's been organised, It look odd. People will feel it is not organise. Kindly generate an updated version in a developer way, then GitHub will then arrange it for publicly-organised

Generated a cleaner, more professional README.md for AfriSync.

Download:

Updated README.md

Also download the command guide:

README_UPDATE_COMMANDS.md

Full ZIP:

afrisync_readme_polished_v3.zip

What changed

The new README is now organised like a proper open-source developer project:

1. Logo and project title
2. Tool badges
3. Why AfriSync exists
4. The African problem it addresses
5. The solution
6. Meaning of the name AfriSync
7. Logo and colour meaning
8. Current features
9. Technology stack with tool badges/logos
10. Architecture diagram
11. Project structure
12. Setup link
13. Project status link
14. Mobile app roadmap link
15. Open-source vision
16. Contribution areas
17. Development philosophy
18. Research context
19. Author
20. License note
Replace this file

Replace your current:

C:\Users\user\OneDrive\Desktop\afrisync\README.md

with the new:

README.md
Push the updated README to GitHub

Run these commands:

cd "C:\Users\user\OneDrive\Desktop\afrisync"
git status --short

Then:

git add README.md

Then:

git commit -m "Improve open-source README documentation"

Then:

git push origin main

After pushing, open your repo:

https://github.com/abdulwahabbadmus001-creator/afrisync

GitHub will automatically render and organise the README nicely on the repo homepage.

README.md
Document
README_UPDATE_COMMANDS.md
Document

Ȍ̘̯̪̍q̪̟M̩̞̀̍
t̯̣̄́L̘̐p̥̒
Library
/
README.md

<p align="center"> <img src="assets/afrisync_connected_africa_logo.png" alt="AfriSync Logo" width="180" /> </p>

<h1 align="center">AfriSync</h1>

<p align="center"> <strong>Offline-first project synchronization for African developers, teams, and infrastructure builders.</strong> </p>

<p align="center"> <a href="https://www.python.org/"><img alt="Python" src="https://img.shields.io/badge/Python-3.14-3776AB?logo=python&logoColor=white"></a> <a href="https://fastapi.tiangolo.com/"><img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-Backend-009688?logo=fastapi&logoColor=white"></a> <a href="https://www.sqlite.org/"><img alt="SQLite" src="https://img.shields.io/badge/SQLite-Offline%20Database-003B57?logo=sqlite&logoColor=white"></a> <a href="https://www.postgresql.org/"><img alt="PostgreSQL" src="https://img.shields.io/badge/PostgreSQL-Production%20Ready-4169E1?logo=postgresql&logoColor=white"></a> <a href="https://www.docker.com/"><img alt="Docker" src="https://img.shields.io/badge/Docker-Deployment-2496ED?logo=docker&logoColor=white"></a> <img alt="Open Source" src="https://img.shields.io/badge/Open%20Source-African%20Developers-0F766E"> </p>

Why AfriSync Exists

Across many African environments, software teams, researchers, NGOs, businesses, and public institutions often work under conditions that mainstream tools do not always design for: unstable internet connectivity, expensive data, fragmented infrastructure, limited cloud access, and the need to keep working even when systems go offline.

AfriSync is built from that reality.

It began as a research-driven software experiment asking a simple question:

What would project collaboration look like if African infrastructure constraints were treated as a design priority, not an afterthought?

AfriSync explores that question by building an offline-first synchronization system where work can continue locally, then sync when connectivity returns. It is both a technical product and a research project around digital resilience, African developer infrastructure, local-first software, and inclusive technology design.

The Problem

Many digital products assume that users always have:

stable internet,
reliable cloud access,
uninterrupted electricity,
low-cost data,
and centralized infrastructure.

That assumption does not always match the reality of builders across Africa.

When connectivity fails, many tools fail with it. Projects stop. Teams lose visibility. Local work becomes disconnected. Small organizations struggle to coordinate. Developers are forced to build around infrastructure gaps instead of building through them.

AfriSync is designed to challenge that pattern.

The Solution

AfriSync allows users to create, edit, manage, and synchronize project work across devices using an offline-first model.

The core idea is simple:

Device A / Local App
        ↓
Remote Sync Server
        ↓
Device B / Local App

Each device keeps working locally. When the network is available, AfriSync synchronizes projects, notes, attachments, activity logs, team roles, notifications, and changes across devices.

This makes AfriSync useful for environments where connectivity is not guaranteed but productivity must continue.

Why the Name “AfriSync”?

AfriSync combines two ideas:

Afri — Africa, African builders, African realities, and African innovation.
Sync — synchronization, collaboration, continuity, and connected progress.

The name reflects the mission: to help African developers and teams build tools that stay connected even when infrastructure is unstable.

Logo Meaning

The AfriSync logo represents the product’s core philosophy.

Logo Element	Meaning
Africa outline	Technology built with African contexts in mind
Database cylinder	Data, storage, sync records, projects, notes, and attachments
Code symbol	Developers, software engineering, and open-source contribution
Circular arrows	Synchronization across devices, teams, and locations
Network nodes	Collaboration, connectivity, and shared digital infrastructure
Colour Meaning
Colour	Meaning
Deep emerald / green	African growth, resilience, agriculture, infrastructure, and renewal
Electric blue / cyan	Technology, data flow, cloud systems, APIs, and synchronization
Amber / orange	Energy, alerts, creativity, urgency, and African sunlight
Charcoal / slate	Professionalism, developer seriousness, dark mode, and product depth
White / soft neutral	Clarity, accessibility, readability, and clean user experience
Current Features

AfriSync currently includes:

Core Offline-First System
Local-first project creation
Local SQLite storage
Remote synchronization server
Multi-device sync testing
Background sync support
Sync status tracking
Conflict detection and resolution foundation
Project Management
Create projects
View projects
Edit projects
Delete projects
Search and filter projects
Project progress tracking
Project details screen
Notes and Attachments
Add project notes
Edit notes
Delete notes
Upload project attachments
Open attachments
Delete attachments
Sync notes and attachments across devices
Team Collaboration
Invite members by username
Assign Viewer or Editor role
Change member role later
Remove members
Editor access for project editing and deletion
Viewer access for read-only collaboration
Authentication and Account Security
User registration
Email-based registration
4-digit email verification code
Verified-only login
Username or email login
Password reset
Continue with Google login
Secure remote sync token
Local session handling
Notifications and Activity Tracking
In-app notifications
Notification badge
Notification dropdown behavior
Activity log
Sync history
Offline and sync-failure notifications
Team invitation and role-change notifications
Admin Dashboard
Admin overview
User management
Enable or disable users
Project soft delete and restore
Transfer project ownership
Member role management
Admin audit logs
CSV export support
Server health overview
Deployment and Packaging Preparation
PostgreSQL-ready backend structure
SQLite-to-PostgreSQL migration script
Deployment readiness checker
Dockerfile
Render deployment template
Production environment examples
Backup script
Desktop launcher preparation
Technology Stack
Tool	Role in AfriSync	Badge
Python	Core backend logic and sync processing	

FastAPI	Remote API, local app API, authentication, sync endpoints	

SQLite	Local-first database for offline device storage	

PostgreSQL	Production-ready remote database target	

HTML/CSS/JavaScript	Browser dashboard interface	
Docker	Container deployment preparation	

GitHub	Open-source hosting and collaboration	

Expo React Native	Planned mobile app conversion	

Architecture
┌──────────────────────────────┐
│        Browser Dashboard      │
│  Projects • Notes • Team • UI │
└───────────────┬──────────────┘
                │
                ▼
┌──────────────────────────────┐
│        Local FastAPI App      │
│   Device A / Device B API     │
└───────────────┬──────────────┘
                │
                ▼
┌──────────────────────────────┐
│        Local SQLite DB        │
│ Offline projects and changes  │
└───────────────┬──────────────┘
                │
                ▼
┌──────────────────────────────┐
│        Sync Engine            │
│ Push • Pull • Conflict checks │
└───────────────┬──────────────┘
                │
                ▼
┌──────────────────────────────┐
│      Remote FastAPI Server    │
│ Auth • Team • Sync • Admin    │
└───────────────┬──────────────┘
                │
                ▼
┌──────────────────────────────┐
│ SQLite now / PostgreSQL later │
│      Production DB target     │
└──────────────────────────────┘
Project Structure
afrisync/
│
├── app/
│   ├── database.py
│   └── sync_engine.py
│
├── templates/
│   └── dashboard.html
│
├── assets/
│   └── afrisync_connected_africa_logo.png
│
├── server.py
├── local_app.py
├── admin_app.py
├── pull_sync.py
├── background_sync.py
├── network.py
│
├── start_afrisync.py
├── desktop_launcher.py
│
├── postgres_schema.sql
├── migrate_server_sqlite_to_postgres.py
├── check_deployment_readiness.py
│
├── README.md
├── SETUP_AND_RUN.md
├── PROJECT_STATUS.md
├── MOBILE_APP_CONVERSION_PLAN.md
└── requirements.txt
How to Run AfriSync

The full setup and run instructions are kept in a separate file to keep this README clean:

👉 Read: SETUP_AND_RUN.md

Basic local development requires four services:

Remote Server  → http://127.0.0.1:8000
Device A       → http://127.0.0.1:8001
Device B       → http://127.0.0.1:8002
Admin          → http://127.0.0.1:8010/admin
Project Status

AfriSync is currently in active development.

The current version proves the core concept:

local-first data entry,
offline project work,
sync between devices,
user authentication,
collaboration roles,
notifications,
admin management,
and production-readiness preparation.

See the simplified development status here:

👉 Read: PROJECT_STATUS.md

Mobile App Roadmap

The next major phase is converting AfriSync into a mobile-first Android/iOS app using Expo React Native while keeping the existing FastAPI backend.

Planned mobile direction:

Android-first testing
Expo React Native + TypeScript
SQLite offline storage
Secure token storage
mobile sync engine
project, notes, attachments, team, notifications, and conflict screens
future iOS support

See the full plan here:

👉 Read: MOBILE_APP_CONVERSION_PLAN.md

Open-Source Vision

AfriSync is open-source because African developer infrastructure should not be built behind closed doors only.

The goal is to create a project that other developers can study, improve, fork, rebuild, and extend for African contexts. In the spirit of collaborative open-source projects such as Linux, AfriSync is being shared early so that builders can contribute to its direction, not merely consume the final product.

This project welcomes developers, designers, researchers, technical writers, product thinkers, and infrastructure builders who care about resilient technology for Africa.

Contribution Areas

AfriSync needs collaboration in these areas:

Area	Contribution Needed
Mobile development	Convert web features into Expo React Native screens
UI/UX design	Improve interface, typography, accessibility, and product polish
Backend engineering	Strengthen FastAPI architecture, testing, and security
Offline-first engineering	Improve sync, conflict resolution, local storage, and retry logic
DevOps	Improve Docker, deployment, monitoring, and PostgreSQL setup
Documentation	Improve setup guides, diagrams, tutorials, and developer onboarding
Research	Connect the project to African infrastructure, policy, and digital resilience problems
Development Philosophy

AfriSync is guided by five principles:

Offline is not failure — users should still work when the internet is unstable.
Africa is not an edge case — African constraints should shape the design from the beginning.
Local-first matters — data should exist close to the user before depending on the cloud.
Collaboration should be resilient — teams should continue building across devices and locations.
Open-source should educate — the code should help new developers learn how real systems are built.
Research Context

AfriSync is part of a broader research and software-building interest in:

African digital infrastructure,
local-first software,
AI and software access gaps,
data sovereignty,
resilient systems,
developer tooling for emerging markets,
and technology that responds to real social and economic constraints.

The project is not only about code. It is also about asking what kind of software architecture makes sense when infrastructure is uneven but ambition is not.

Author

Wahab Opeyemi Badmus
Researcher, software builder, and AI governance enthusiast working at the intersection of technology, research, education, and African development.

License

This project is intended to be open-source. A formal license file should be added before major external contribution begins.

Recommended license: MIT License.

Closing Note

AfriSync is still evolving, but the mission is clear:

Build tools that understand African realities and give developers the power to keep building — online, offline, and across borders.