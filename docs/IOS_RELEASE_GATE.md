# iOS Release Gate (Non-Skippable)

Use this gate before any TestFlight/App Store submission.

## 1) Wrapper Build Gate
- [ ] `cd mobile/ios-wrapper`
- [ ] `npm install`
- [ ] `npm run preflight`
- [ ] `npm run sync:ios`
- [ ] Open Xcode project and verify no build-time dependency errors.

## 2) Auth + Access Gate
- [ ] Google sign-in works inside iOS wrapper.
- [ ] Domain restrictions still enforced (`@eips.ca` behavior unchanged).
- [ ] Non-authorized account gets blocked correctly.

## 3) Core Workflow Gate
- [ ] Enter marks and run `Check Eligibility`.
- [ ] Program list renders without overflow.
- [ ] Program details open reliably.
- [ ] Meeting decision + note persist.
- [ ] `Print Packet` works in iOS share/print flow.

## 4) Device Behavior Gate
- [ ] Safe areas respected (top notch + home indicator).
- [ ] Keyboard does not hide required controls/inputs.
- [ ] Scroll performance remains smooth during long result lists.
- [ ] Orientation change does not break layout.

## 5) Accessibility Gate
- [ ] Dynamic text scaling remains readable.
- [ ] Focus/selection states are visible.
- [ ] Contrast checks pass in all key panels/cards/actions.

## 6) Ops Gate
- [ ] Failure behavior verified with network disabled.
- [ ] Recovery behavior verified after network returns.
- [ ] Support/logging process documented for iOS-specific incidents.

## Exit Criteria
- [ ] Two consecutive pilot weeks without blocker defects.
- [ ] No unresolved P1/P2 issues in run/details/packet flows.
