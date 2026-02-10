# Sprint Slice

Use this file to keep each Codex session focused and low-pass.

## Current Objective (2026-02-10)
Stabilize the staff-ready web app MVP and modularize Apps Script for low-risk maintenance.

## Slice Backlog
- [x] Slice 1: Security lockdown (signed-in access, token/domain gate, rate limit, minimize callable functions)
- [ ] Slice 2: Backend response contract (`meta`, `detailsByKey`, `rowKeysByView`)
- [ ] Slice 3: Web UI MVP upgrades (paste parser, search/filter/sort, details drawer, star)
- [ ] Slice 4: Export + performance + lightweight audit (iframe PDF, caching, audit sheet)
- [ ] Slice 5: QA + release verification
- [ ] Slice 6: Apps Script structural modularization + guardrails

## Working Rules
- Keep changes surgical; no unrelated refactors.
- Keep response compatibility while extending backend payloads.
- For web app changes, run `tools/validate-webapp-surface.ps1` before commit.
- Append short outcomes to `docs/WORK_LOG.md` after each slice.

## Done Log
- [x] 2026-02-10: Added decision/slice/QA docs + validation scaffold to reduce future passes.
- [x] 2026-02-10: Completed security slice (DOMAIN manifest, `@eips.ca` gate, request throttling, minimized callable server surface).
- [x] 2026-02-10: Switched to personal-deploy security model (`ANYONE` + Google ID token domain validation), strict payload key allowlists, and local `?mock=1` web UI preview workflow.
