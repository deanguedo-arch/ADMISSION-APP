# Agent Operating Rules (POST SECONDARY SCRAPING)

These rules exist so every new Codex chat starts with the same context and stays token-efficient.

## Always do first (every session)
- Read `docs/PROJECT_CONTEXT.md`
- Read `docs/DECISIONS.md`
- Read `docs/SPRINT_SLICE.md`
- Read `docs/WORK_LOG.md` (last ~20 lines is enough)
- If you change code/data/docs: append a short entry to `docs/WORK_LOG.md`
- If a chat gets long: run `tools/handoff.ps1` and start a new chat using `docs/SESSION_HANDOFF.md`.

## Working style
- Prefer small, surgical changes; do not refactor unrelated code.
- Keep outputs concise; avoid re-explaining project basics already in `docs/PROJECT_CONTEXT.md`.
- When proposing decisions, ask 1-3 concrete questions max.
- For web app changes, run `tools/validate-webapp-surface.ps1` before commit/push.

## Source of truth
- Google Sheets is the staff UI.
- The canonical dataset is `data/ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv`.
- The scraper/extractor pipeline is responsible for producing structured fields like `Avg_Total` (not Sheets).
