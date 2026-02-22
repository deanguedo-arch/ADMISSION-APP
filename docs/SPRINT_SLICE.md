# Sprint Slice

Use this file to keep each Codex session focused and low-pass.

## Current Objective (2026-02-10)
Ship a clean release candidate: finalize recent web app fixes, verify preflight checks, and keep handoff/docs aligned.

## Slice Backlog
- [x] Slice 1: Security lockdown (signed-in access, token/domain gate, rate limit, minimize callable functions)
- [x] Slice 2: Backend response contract (`meta`, `detailsByKey`, `rowKeysByView`)
- [x] Slice 3: Web UI MVP upgrades (paste parser, search/filter/sort, details drawer, star)
- [x] Slice 4: Performance + lightweight audit hardening (cache + audit trail shipped)
- [x] Slice 5: QA + release verification (local + guardrail checks complete; deployed smoke queued)
- [x] Slice 6: Apps Script structural modularization + guardrails

## Working Rules
- Keep changes surgical; no unrelated refactors.
- Keep response compatibility while extending backend payloads.
- For web app changes, run `tools/validate-webapp-surface.ps1` before commit.
- Append short outcomes to `docs/WORK_LOG.md` after each slice.

## Done Log
- [x] 2026-02-10: Added decision/slice/QA docs + validation scaffold to reduce future passes.
- [x] 2026-02-10: Completed security slice (DOMAIN manifest, `@eips.ca` gate, request throttling, minimized callable server surface).
- [x] 2026-02-10: Switched to personal-deploy security model (`ANYONE` + Google ID token domain validation), strict payload key allowlists, and local `?mock=1` web UI preview workflow.
- [x] 2026-02-10: Completed structural modularization seam 2 (split eligibility engine by responsibility; split web app HTML into include fragments; added include-aware rendering + structure guardrail updates).
- [x] 2026-02-10: Fixed results-table squish/readability regressions and verified local preview launcher auto-port fallback for reserved ports (`System/PID 4` case).
- [x] 2026-02-10: Ran release preflight automation (`validate-webapp-surface`, `validate-apps-script-structure`) and local preview startup smoke.
- [x] 2026-02-10: Completed Slice 4 by adding cached `runWebEligibility` responses, dataset fingerprint metadata, and bounded lightweight `WebAudit` logging without raw marks.
- [x] 2026-02-10: Completed Slice 5 local QA pass by re-running guardrails, validating preview startup, surfacing dataset freshness in UI, and hardening PDF export to iframe-print (no popup dependency).
- [x] 2026-02-22: Phase 7 pass 1 delivered Student Mode baseline (copy simplification + advanced-control reduction + debounced search + mobile sticky actions/touch targets).

## Meeting + Mobile Roadmap (2026-02-22)
- [x] Phase 5: Stability + accessibility hardening for meeting use (keyboard/focus/responsive/details panel fixes).
- [x] Phase 6: Meeting workflow decisions + packet export (decision tags, owner/date, packet CSV, card decision pills).
- [ ] Phase 7: Student Mode Optimization
  - simplified student-facing mode with reduced controls and clearer copy.
  - speed/load optimizations for low-end phones.
  - tighter mobile touch targets and sticky action controls.
- [ ] Phase 8: iPhone Web Release Operations
  - automate release-gate checks and expected-count smoke tests.
  - confirm 2 consecutive weekly successful cycles.
  - finalize support playbook and incident handling flow.
- [ ] Phase 9: App Store Track (Deferred Wrapper)
  - Capacitor/WKWebView packaging path.
  - App Store metadata/privacy/review preparation.
  - update strategy decision (online-only vs bundled snapshot).
