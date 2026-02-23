# Web App QA Checklist

Run this before each production push affecting `apps_script/`.

## 1) Preflight
- [ ] Run `.\tools\validate-webapp-surface.ps1`
- [ ] Run `.\tools\validate-apps-script-structure.ps1`
- [ ] Confirm `apps_script/appsscript.json` has:
  - [ ] `webapp.access = ANYONE`
  - [ ] `timeZone = America/Edmonton`
- [ ] If `WebApp*.html` changed, verify local preview loads with `?mock=1`.

## 2) Security
- [ ] Domain user can load deployed web app.
- [ ] Non-domain user is blocked after sign-in validation.
- [ ] Google sign-in requires configured client ID.
- [ ] ID token validation enforces: aud/iss/exp/email_verified/hosted domain.
- [ ] `getWebAppBootstrapData` enforces domain gate.
- [ ] `runWebEligibility` enforces domain gate.
- [ ] Rate limit triggers friendly message under rapid repeated runs.
- [ ] Only intended server functions are callable via client.

## 3) Data + Contract
- [ ] `runWebEligibility` returns current baseline fields:
  - [ ] `generatedAt`
  - [ ] `headers`
  - [ ] `summary`
  - [ ] `results` (`all`, `eligible`, `ineligible`, `uncheckable`)
- [ ] Extended payload fields present and non-breaking:
  - [ ] `meta`
  - [ ] `detailsByKey`
  - [ ] `rowKeysByView`
- [ ] Dataset freshness stamp is visible in UI.

## 4) UX
- [ ] Student Inputs does not show Paste Transcript controls.
- [ ] Student Inputs actions are simplified to `Check Eligibility` + `Reset Form` (no in-panel CSV/PDF buttons).
- [ ] Search works across institution/program/credential.
- [ ] Filter tabs work (`Likely ineligible`, `Likely eligible`, `Uncheckable`, `Shortlist`, `All`).
- [ ] Sort options work (including closest-to-eligible where computable).
- [ ] Row click opens details drawer with matching row content.
- [ ] Program Explorer tab works with shared search/filter/sort controls.
- [ ] Requirements section starts expanded by default in details.
- [ ] Meeting Workflow block renders fully (not clipped) at desktop widths.
- [ ] Decision tags (`Apply`, `Hold`, `Not now`) save per program and show a decision pill on result cards.
- [ ] Meeting workflow shows decision chips + note only (no owner/follow-up fields).
- [ ] Meeting notes can be edited/cleared and `Print Packet` count updates correctly.
- [ ] Details drawer in Eligibility Results does not include a `Notes` section.
- [ ] Compare tools are available under `Advanced Tools` and the section is collapsed by default.
- [ ] `Advanced Tools` contains comparison tools only (no extra workflow toggles in normal UI).
- [ ] Student Mode UI remnants are absent.
- [ ] Defaults load as 5 named rows and 1 elective override row.

## 5) Export
- [ ] `Print Packet` opens a styled PDF packet (no CSV fallback) and includes:
  - [ ] filtered visible list
  - [ ] selected detail summary
  - [ ] meeting decision/note summary
- [ ] Packet header includes generation timestamp + dataset context.

## 6) Performance + Ops
- [ ] Repeated runs are faster due to cache hits.
- [ ] Cache invalidation works after dataset refresh.
- [ ] Audit entry writes timestamp + identity key + summary counts.
- [ ] Audit does not persist raw student marks.
- [ ] Run action shows loading skeleton and completes with runtime status text.
- [ ] Optional debug telemetry (if enabled) remains hidden from default counselor workflow.

## 7) Release
- [ ] Commit message clearly identifies slice.
- [ ] `docs/WORK_LOG.md` updated with outcome.
- [ ] Push to `main` completed.
- [ ] Deployed web app smoke-tested once.

## 8) Accessibility + Responsive Hardening
- [ ] Keyboard-only flow works for core actions (run, filter, select card, open details).
- [ ] Focus indicator is visible on buttons, fields, links, and result cards.
- [ ] Live status regions announce updates (`status`, `rows stamp`).
- [ ] At ~1280-1536 desktop widths, details panel content does not collapse into clipped/overlapped blocks.
- [ ] At `<=980px`, mobile app-shell behavior is active (`body[data-screen]` + bottom nav tabs).
- [ ] At `<=980px`, only one region scrolls per screen (no page-level double-scroll jitter).
- [ ] Header does not "stick/release" jitter on iPhone Safari while list scrolls.
- [ ] Bottom tabs stay visible on Inputs/Results/Pinned/Compare; details screen intentionally hides tabs.
- [ ] Mobile Results/Pinned use contextual bottom action bar (`Clear`, `Print Packet`) and actions are not clipped.
- [ ] Mobile filters open via single `Filters` button and apply from drawer (no stacked inline filter controls).
- [ ] Mobile result cards do not show 4 stacked actions; tap card opens Details, inline action is Pin only.
- [ ] Mobile Details has Back behavior that returns to prior tab context.
- [ ] Mobile list paging works (`Load more` chunking) and remains responsive with large result sets.
- [ ] No horizontal overflow at `320px` width.

## 9) iOS Wrapper Readiness
- [ ] `WebApp.html` includes `viewport-fit=cover` and mobile web app meta tags.
- [ ] Safe-area insets are respected (top + bottom) for header and sticky actions.
- [ ] iOS Safari does not auto-zoom on inputs (effective 16px+ input text).
- [ ] Sticky toolbar + action bar remain usable with keyboard open on iPhone viewport.
- [ ] `mobile/ios-wrapper` preflight + sync/open commands run successfully.
- [ ] `docs/IOS_RELEASE_GATE.md` non-skippable gates are completed on physical iPhone device(s).
