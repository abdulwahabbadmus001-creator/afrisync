AfriSync Setup and Local Run Guide

This file explains how to set up and run AfriSync locally after cloning the repository from GitHub.

AfriSync is currently a Python/FastAPI offline-first web application with a local dashboard, remote sync server, admin dashboard, and multi-device testing support.

1. Requirements

Install these first:

Python 3.11 or newer

Git

A modern browser such as Chrome, Edge, or Firefox

Windows PowerShell

Optional for later:

PostgreSQL

Docker

Google OAuth Client ID

Gmail App Password for real email sending

2. Clone the repository

git clone https://github.com/abdulwahabbadmus001-creator/afrisync.git
cd afrisync

3. Create a virtual environment

python -m venv .venv

Activate it:

.\.venv\Scripts\Activate.ps1

If PowerShell blocks activation, run:

Set-ExecutionPolicy -Scope CurrentUser RemoteSigned

Then activate again:

.\.venv\Scripts\Activate.ps1

4. Install dependencies

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

If requirements.txt is not available, install the core packages manually:

python -m pip install fastapi uvicorn requests pydantic python-multipart itsdangerous passlib bcrypt email-validator jinja2

5. Run the remote sync server

Open Terminal 1:

.\run_remote_server.ps1

Expected result:

Uvicorn running on http://127.0.0.1:8000
Application startup complete.

Check server health:

http://127.0.0.1:8000/health

6. Run Device A

Open Terminal 2:

.\run_device_a.ps1

Open in browser:

http://127.0.0.1:8001

Device A simulates one local user device.

7. Run Device B

Open Terminal 3:

.\run_device_b.ps1

Open in browser:

http://127.0.0.1:8002

Device B simulates another local device.

8. Run Admin Dashboard

Open Terminal 4:

.\run_admin_dashboard.ps1

Open:

http://127.0.0.1:8010/admin

Default local admin login:

Username: admin
Password: admin12345

Change the admin password before any real deployment.

9. Recommended local test flow

Start the remote server.

Start Device A.

Start Device B.

Register a user on Device A.

Verify the account if email verification is enabled.

Create a project on Device A.

Add notes and attachments.

Click Sync Now.

Log in on Device B.

Click Sync Now.

Confirm the project appears on Device B.

Invite another user.

Change user role from Viewer to Editor.

Test notifications.

Check Admin Dashboard.

10. Testing on phone browser

Your phone and laptop must be on the same Wi-Fi network.

Run these scripts instead of the normal local-only scripts:

.\run_remote_server_for_phone.ps1

.\run_device_a_for_phone.ps1

Then run:

.\show_phone_test_urls.ps1

Open the shown Device A URL on your phone browser.

Example:

http://192.168.1.10:8001

Google login on phone requires adding the phone-test origin to Google Cloud OAuth settings.

11. Environment configuration

Do not commit real secret files to GitHub.

Files like these should remain local only:

afrisync_email_config.ps1
afrisync_google_config.ps1
afrisync_postgres_config.ps1
afrisync_production_config.ps1
sync_secret.key
.env

Use the .example.ps1 files as templates.

12. PostgreSQL mode

SQLite is the default local development database.

PostgreSQL is optional and intended for production-style testing.

Do not run PostgreSQL scripts until PostgreSQL is installed, the database is created, and the database URL is configured.

13. Desktop launcher

AfriSync includes a Windows launcher system.

Check launcher requirements:

.\run_launcher_check.ps1

Run launcher:

.\run_desktop_launcher.ps1

Build EXE:

.\build_desktop_exe.ps1

14. Common issue: No module named uvicorn

Install dependencies inside the virtual environment:

.\.venv\Scripts\python.exe -m pip install -r requirements.txt

Then run the app again.

15. Common issue: .venv has no pip

Repair it:

.\.venv\Scripts\python.exe -m ensurepip --upgrade
.\.venv\Scripts\python.exe -m pip install --upgrade pip

If repair fails, delete and recreate .venv:

Remove-Item -Recurse -Force .venv
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

16. Development note

AfriSync is currently a working prototype and research-driven engineering project. It is suitable for learning, testing, and open-source collaboration. Production deployment requires additional security hardening, hosted PostgreSQL, real SMTP configuration, environment secrets, logging, monitoring, and tests.