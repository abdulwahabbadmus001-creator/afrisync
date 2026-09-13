AfriSync Mobile App Conversion Plan

AfriSync currently works as a browser-based web app. The next major goal is to convert it into a proper Android/iOS mobile app.

Recommended approach

Do not rewrite the entire project from zero.

Keep the current Python/FastAPI backend and build a new mobile frontend.

Current backend: FastAPI + SQLite/PostgreSQL-ready sync server
New mobile app: Expo React Native + TypeScript

Future structure

afrisync/
├── server.py
├── local_app.py
├── admin_app.py
├── app/
├── templates/
└── afrisync-mobile/
    ├── app/
    ├── components/
    ├── services/
    ├── storage/
    ├── sync/
    └── package.json

Mobile technologies

Recommended tools:

Expo React Native

TypeScript

Expo SQLite

Expo SecureStore

Expo FileSystem

NetInfo

React Navigation or Expo Router

FastAPI backend API

Mobile screens to build

Welcome screen

Login screen

Register screen

Email verification screen

Google sign-in screen

Forgot password screen

Overview screen

Projects screen

Create project screen

Project details screen

Notes screen

Attachments screen

Team members screen

Sync center screen

Notifications screen

Errors screen

Conflicts screen

Settings screen

Mobile sync behavior

The mobile app should preserve the same offline-first idea:

User creates/edits data on phone
        ↓
Data saves first into mobile SQLite
        ↓
Sync queue marks changes as pending
        ↓
When internet returns, app pushes changes to server
        ↓
Phone pulls updates from server

Collaboration needs

This part of the project needs collaborators with experience in:

Expo React Native

mobile UI design

offline-first architecture

SQLite on mobile

secure token storage

background sync

mobile file upload

Android builds

iOS builds

testing and deployment

First mobile milestone

The first mobile version should focus only on:

Authentication

Local project list

Create project

Offline saving

Manual sync

Pull projects from server

Basic notifications

After that, notes, attachments, teams, conflicts, and admin-connected features can be added.

Goal

The mobile version should make AfriSync useful to people who work from phones first, especially in environments where laptops, stable internet, and constant power are not always guaranteed.