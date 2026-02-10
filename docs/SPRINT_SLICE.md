# Sprint Slice

Use this file to keep each Codex session focused and low-pass.

## Current Objective (2026-02-10)
Ship a clean release candidate: finalize recent web app fixes, verify preflight checks, and keep handoff/docs aligned.

## Slice Backlog
- [x] Slice 1: Security lockdown (signed-in access, token/domain gate, rate limit, minimize callable functions)
- [x] Slice 2: Backend response contract (`meta`, `detailsByKey`, `rowKeysByView`)
- [x] Slice 3: Web UI MVP upgrades (paste parser, search/filter/sort, details drawer, star)
- [ ] Slice 4: Performance + lightweight audit hardening (exports are in place; caching/audit follow-up remains)
- [ ] Slice 5: QA + release verification (preflight complete; full deployed manual smoke still pending)
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
