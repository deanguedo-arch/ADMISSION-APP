# Web App QA Checklist

Run this before each production push affecting `apps_script/`.

## 1) Preflight
- [ ] Run `.\tools\validate-webapp-surface.ps1`
- [ ] Confirm `apps_script/appsscript.json` has:
  - [ ] `webapp.access = DOMAIN`
  - [ ] `timeZone = America/Edmonton`

## 2) Security
- [ ] Domain user can load deployed web app.
- [ ] Non-domain user is blocked (or cannot access due to deployment policy).
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
- [ ] Filter tabs work (`Eligible`, `Missing`, `Uncheckable`, `All`, `Starred`).
- [ ] Sort options work (including closest-to-eligible where computable).
- [ ] Row click opens details drawer with matching row content.

## 5) Export
- [ ] CSV export works for current view.
- [ ] CSV export works for all rows.
- [ ] PDF export works via iframe print (no popup dependency).
- [ ] Export includes dataset stamp + generation time.

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
