# iOS App Store Readiness (Deferred)

This project is shipping web-first now (Safari/Home Screen).  
This document locks the later App Store direction so future work is consistent.

## Locked Future Direction
- Wrapper target: `Capacitor` + iOS `WKWebView`.
- Runtime source: public student snapshot URL (or bundled static snapshot build).
- Staff Apps Script app remains separate and auth-gated.

## What Is Deferred (Not In Current Slice)
- Creating Xcode project/app bundle.
- App Store Connect setup and submission.
- Native push notifications/background sync.
- Native-only UI rewrite.

## App Store Compliance Checklist (Future)
- [ ] Privacy Policy URL published and linked in app metadata.
- [ ] Terms/disclaimer text aligned with advisory-only admissions guidance.
- [ ] Age rating reviewed.
- [ ] Data handling statement documented (what is and is not persisted).
- [ ] Contact/support email documented.
- [ ] App review notes include test account/instructions if needed.

## Wrapper Readiness Technical Checklist (Future)
- [ ] Confirm web app works fully in WKWebView (forms, exports, links).
- [ ] Decide online-only vs bundled offline snapshot strategy.
- [ ] Add in-app refresh strategy for snapshot dataset updates.
- [ ] Define cache/version invalidation rules.
- [ ] Define deep-link behavior and URL handling.
- [ ] Define release pipeline from snapshot build to iOS bundle updates.

## Known Review Risks + Mitigations
- Risk: App considered too thin as a simple website shell.
  - Mitigation: Include clear iOS-specific packaging value (install stability, managed updates, support).
- Risk: Insufficient disclosure for advisory admissions decisions.
  - Mitigation: Show explicit advisory language and source verification guidance in-app.
- Risk: Stale data concerns.
  - Mitigation: Always display dataset date and maintain regular refresh cadence.

## Go/No-Go Entry Criteria For App Store Track
- [ ] Home Screen web flow is stable across at least two iOS versions.
- [ ] Public release gate has passed for at least two consecutive weekly cycles.
- [ ] Support playbook exists for student incidents.
