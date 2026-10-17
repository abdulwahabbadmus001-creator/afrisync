# AfriSync Mobile App v1

AfriSync Mobile is the first Expo React Native version of AfriSync. It keeps the existing Python/FastAPI backend and starts the mobile layer with:

- Email/password authentication screens
- Email verification screen
- Password reset screen
- Mobile dashboard
- Projects screen
- Create project screen
- Project details + notes
- Notifications
- Sync Center
- Settings screen for backend URL
- Offline-first SQLite storage
- Secure session storage
- Network-aware sync queue

## Architecture

```text
AfriSync Mobile App
  ↓ local-first writes
Expo SQLite database
  ↓ sync queue
AfriSync FastAPI backend
  ↓
Remote server database
```

## Important backend URL rule

On your phone, `127.0.0.1` means the phone itself, not your laptop.

For phone testing, run the AfriSync backend on your laptop and use your laptop Wi-Fi IP in the mobile Settings screen:

```text
http://YOUR-LAPTOP-IP:8000
```

Example:

```text
http://192.168.1.10:8000
```

## Start commands

```powershell
cd "C:\Users\user\OneDrive\Desktop\afrisync\afrisync-mobile"
npm install
npx expo install expo-sqlite expo-secure-store expo-file-system @react-native-community/netinfo react-native-safe-area-context
npx expo start
```

Then open with Expo Go on Android or use an emulator.

## First test flow

1. Start your AfriSync backend on your laptop.
2. Open AfriSync Mobile.
3. Go to Settings.
4. Set the backend URL to your laptop IP.
5. Test backend connection.
6. Register or log in.
7. Create a project.
8. Turn off internet and create another project/note.
9. Turn internet back on.
10. Open Sync Center and tap Sync Now.

## Development note

Google mobile sign-in is not fully enabled in this first version. For v1, the priority is stabilizing email/password, SQLite offline storage, and sync queue behavior. Google OAuth for native mobile requires a separate Android/iOS OAuth configuration.
