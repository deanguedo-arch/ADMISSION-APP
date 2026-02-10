# Sprint Slice

Use this file to keep each Codex session focused and low-pass.

## Current Objective (2026-02-10)
Harden and ship a staff-ready web app MVP without changing admissions rule intent.

## Slice Backlog
- [x] Slice 1: Security lockdown (domain-only access, domain gate, rate limit, minimize callable functions)
- [ ] Slice 2: Backend response contract (`meta`, `detailsByKey`, `rowKeysByView`)
- [ ] Slice 3: Web UI MVP upgrades (paste parser, search/filter/sort, details drawer, star)
- [ ] Slice 4: Export + performance + lightweight audit (iframe PDF, caching, audit sheet)
- [ ] Slice 5: QA + release verification

## Working Rules
- Keep changes surgical; no unrelated refactors.
- Keep response compatibility while extending backend payloads.
- For web app changes, run `tools/validate-webapp-surface.ps1` before commit.
- Append short outcomes to `docs/WORK_LOG.md` after each slice.

## Done Log
- [x] 2026-02-10: Added decision/slice/QA docs + validation scaffold to reduce future passes.
- [x] 2026-02-10: Completed security slice (DOMAIN manifest, `@eips.ca` gate, request throttling, minimized callable server surface).
