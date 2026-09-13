AfriSync Project Status

This file gives a simple explanation of what has been built, what works now, and what the project plans to become.

Current stage

AfriSync is currently a working offline-first web application prototype.

It is not just a UI demo. It has a real backend, local databases, remote sync logic, admin dashboard, authentication features, notifications, team roles, and deployment preparation files.

What has been built so far

1. Offline-first project system

Users can create and manage projects locally. The app saves work on the local device first, then syncs later when the remote server is available.

2. Remote sync server

A FastAPI server receives project, note, attachment, team, and sync data from local devices.

3. Multi-device testing

Device A and Device B can run on the same laptop to simulate two different devices syncing through the same remote server.

4. Authentication

The app supports account registration, login, session handling, password reset, email verification, and Google login support.

5. Email verification

New users can verify accounts using a 4-digit code sent to their email when SMTP is configured.

6. Google sign-in

Users can sign in with Google using a Google OAuth Client ID.

7. Project notes

Users can attach notes to projects and sync those notes across devices.

8. Project attachments

Users can upload and manage files attached to a project.

9. Team collaboration

Project owners can invite members, assign roles, remove members, and change user roles.

10. Viewer and Editor roles

Viewers can view shared work. Editors can contribute and manage project work based on permission rules.

11. Notifications

The app can show in-app notifications for project activity, sync activity, invitations, role changes, conflicts, and errors.

12. Errors and conflicts

The app has dedicated spaces for failed syncs, errors, and conflict tracking.

13. Admin dashboard

Admins can monitor users, projects, team members, sync state, project status, and system health.

14. Admin actions

Admin can enable/disable users, soft-delete or restore projects, transfer project ownership, update member roles, and export records.

15. Deployment preparation

The project includes production readiness files, .gitignore, Docker support, Render configuration, health checks, and environment templates.

16. PostgreSQL-ready migration layer

The current default is SQLite. PostgreSQL support has been prepared for production migration later.

17. Desktop launcher

A Windows launcher has been added to help start the remote server, Device A, Device B, and Admin Dashboard from one place.

18. Responsive access

The current web version can be accessed from desktop, laptop, tablet, and phone browser when configured correctly.

What is working now

The current local version supports:

Remote Server: http://127.0.0.1:8000
Device A:      http://127.0.0.1:8001
Device B:      http://127.0.0.1:8002
Admin:         http://127.0.0.1:8010/admin

The main development database is still SQLite.

Why the project matters

AfriSync is built around the idea that African software should not always assume perfect internet access.

Many teams still need to work when internet access is slow, unstable, expensive, or unavailable. AfriSync explores how local-first and offline-first systems can support productivity in those environments.

The project is part software engineering and part research into infrastructure-aware technology for African users.

Immediate next improvements

The next improvements should focus on stability and collaboration:

Clean final UI/UX polish

Add automated tests

Improve error handling

Improve sync conflict resolution

Add better setup documentation

Improve mobile browser experience

Add contribution guide

Add license file

Prepare hosted demo

Begin React Native mobile version

Mobile app plan

The mobile app should not simply copy the web dashboard. It should be built as a proper mobile-first experience.

Recommended mobile stack:

Expo React Native
TypeScript
SQLite local storage
SecureStore for tokens
FileSystem for attachments
NetInfo for connectivity status
FastAPI backend reuse

Planned mobile screens:

Welcome / onboarding

Login

Register

Email verification

Google sign-in

Forgot password

Overview

Projects

Create project

Project details

Notes

Attachments

Team members

Sync center

Notifications

Errors

Conflicts

Settings

Collaboration request

I am seeking collaborators to help convert AfriSync into a full mobile app for Android and iOS.

Needed collaboration areas:

React Native / Expo development

UI/UX design

mobile offline storage

sync engine design

backend API hardening

PostgreSQL deployment

cloud deployment

testing

documentation

open-source community building

The aim is to build a practical open-source product that can benefit African developers, students, small teams, field workers, and organizations working in real infrastructure conditions.

Long-term vision

AfriSync should become:

A local-first collaboration platform for African builders.

Long-term possibilities:

Android app

iOS app

hosted web version

desktop app

organization accounts

field-data collection mode

SME project management mode

education/team learning mode

public plugin architecture

open-source contributor ecosystem

Current development priority

The current priority is:

Push AfriSync Web v1 to GitHub.
Stabilize the web version.
Invite collaborators.
Begin the mobile app conversion.