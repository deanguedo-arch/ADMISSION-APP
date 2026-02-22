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
- [ ] Paste parser correctly handles:
  - [ ] `English 30-1 82`
  - [ ] `English 30-1: 82%`
  - [ ] `course,mark` CSV lines
- [ ] Search works across institution/program/credential.
- [ ] Filter tabs work (`Likely ineligible`, `Likely eligible`, `Uncheckable`, `Shortlist`, `All`).
- [ ] Sort options work (including closest-to-eligible where computable).
- [ ] Row click opens details drawer with matching row content.
- [ ] Program Explorer tab works with shared search/filter/sort controls.
- [ ] Requirements section starts expanded by default in details.
- [ ] Meeting Workflow block renders fully (not clipped) at desktop widths.
- [ ] Decision tags (`Apply`, `Hold`, `Not now`) save per program and show a decision pill on result cards.
- [ ] Meeting Owner and Follow-up Date fields save/reload in the same browser session.
- [ ] Meeting notes can be edited/cleared and `Export Packet` count updates correctly.
- [ ] Student Mode toggle updates copy and simplifies controls (advanced filters/meeting compare actions hidden).
- [ ] Student Mode keeps results usable with search + card details flow on desktop and mobile.

## 5) Export
- [ ] CSV export works for current view.
- [ ] CSV export works for all rows.
- [ ] PDF export works via iframe print (no popup dependency).
- [ ] Export includes dataset stamp + generation time.
- [ ] `Export Packet` includes workflow fields (`Decision`, `Owner`, `Follow-up Date`, `Snapshot`, `Confidence`, `Next Step`, `Source URL`, `Meeting Note`).

## 6) Performance + Ops
- [ ] Repeated runs are faster due to cache hits.
- [ ] Cache invalidation works after dataset refresh.
- [ ] Audit entry writes timestamp + identity key + summary counts.
- [ ] Audit does not persist raw student marks.

## 7) Release
- [ ] Commit message clearly identifies slice.
- [ ] `docs/WORK_LOG.md` updated with outcome.
- [ ] Push to `main` completed.
- [ ] Deployed web app smoke-tested once.

## 8) Accessibility + Responsive Hardening
- [ ] Keyboard-only flow works for core actions (run, filter, select card, open details).
- [ ] Focus indicator is visible on buttons, fields, links, and result cards.
- [ ] Live status regions announce updates (`status`, `paste status`, `rows stamp`).
- [ ] At ~1280-1536 desktop widths, details panel content does not collapse into clipped/overlapped blocks.
- [ ] At `<=980px`, toolbar controls stack cleanly and details sections remain readable.
- [ ] At `<=980px`, run actions remain reachable with sticky behavior and 44px targets.
