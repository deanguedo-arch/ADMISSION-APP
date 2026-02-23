# iOS Wrapper Readiness (2026-02-22)

This checklist tracks what is required to move the current web app into a production iOS wrapper release.

## Completed in web layer
- `viewport-fit=cover` + Apple mobile web app meta tags are present in `apps_script/WebApp.html`.
- Safe-area aware padding is applied to shell and sticky action regions in `apps_script/WebAppStyles.html`.
- Touch targets are normalized to 44px+ for primary controls.
- Responsive layouts are hardened for desktop/tablet/mobile without horizontal overflow.
- Optional telemetry internals are retained for debug instrumentation (not exposed in normal UI).

## Completed in wrapper scaffold
- Created in-repo Capacitor iOS wrapper at `mobile/ios-wrapper/`.
- Added environment-driven deployment URL config in `mobile/ios-wrapper/capacitor.config.ts`.
- Added non-skippable local preflight script:
  - `mobile/ios-wrapper/scripts/preflight.sh`
- Added wrapper operation commands:
  - `npm run preflight`
  - `npm run sync:ios`
  - `npm run open:ios`
  - `npm run run:ios`
- Added iOS release gate checklist:
  - `docs/IOS_RELEASE_GATE.md`

## Remaining for Capacitor/App Store track
- Add native shell behavior:
  - status bar style/contrast
  - keyboard avoidance with sticky controls
  - in-app file export/share handoff
  - offline/poor-network fallback messaging
- Add production monitoring:
  - crash reporting
  - runtime web view error capture
  - privacy-safe analytics export cadence
- App Store prep:
  - privacy questionnaire and data-use disclosures
  - screenshots (iPhone + iPad) and metadata copy
  - TestFlight pilot with counsellor workflow acceptance

## Release gate
- Two consecutive pilot weeks with no blocker defects in:
  - run eligibility flow
  - details review flow
  - packet export/print/share flow
  - keyboard + safe-area behavior on current iPhone devices
