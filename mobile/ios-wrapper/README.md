# iOS Wrapper (Capacitor)

This folder contains the production iOS wrapper scaffold for the Next Step Admissions web app.

## Why this exists
- Keeps one responsive web UI codebase.
- Adds non-skippable iOS packaging/runtime checks for App Store track.
- Provides repeatable wrapper sync/open flow for release operations.

## 1) Configure deployment URL
1. Copy `.env.example` to `.env`.
2. Set `NEXTSTEP_WEBAPP_URL` to your deployed Apps Script web app URL.

Example:
```bash
cp .env.example .env
```

## 2) Install dependencies
```bash
npm install
```

## 3) Run preflight (non-skippable)
```bash
npm run preflight
```

Preflight checks:
- required local tools (`node`, `npm`, `npx`, `xcodebuild`, `xcrun`)
- URL format + basic HTTP probe
- CocoaPods warning if missing

## 4) Sync and open iOS project
```bash
npm run sync:ios
npm run open:ios
```

Or one command:
```bash
npm run run:ios
```

## 5) Runtime plugins included
- `@capacitor/keyboard`
- `@capacitor/status-bar`
- `@capacitor/share`
- `@capacitor/haptics`
- `@capacitor/app`

## Notes
- Wrapper is configured for remote-hosted web app (`server.url` in `capacitor.config.ts`).
- Keep access control/auth gates in Apps Script as source-of-truth.
- Do final iPhone QA on physical devices before TestFlight/App Store submission.
