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

<!-- STAX_PROJECT_CONTROL_PROTOCOL_V1 -->
# STAX Project-Control Protocol

You are working under STAX project-control protocol.

At the start of every Codex turn in this repo:

1. Read `.stax/turn-contract.json` if it exists.
2. Read `.stax/status.json` if it exists.
3. If the verdict is `Reject`, `Provisional`, or `Human review`, read `.stax/next-codex-prompt.md` and treat it as the immediate correction task unless the user explicitly says to ignore STAX for this turn.
4. Include the exact `STAX_ACK ...` line from `.stax/turn-contract.json` in `.stax/codex-report.md`.
5. If `.stax/turn-contract.json` is missing, say so in `.stax/codex-report.md` and do not claim completion.
6. If `.stax/task.md` is blank, write the user's current objective there before editing.
7. Before handoff or a protected boundary, run STAX preflight in observer mode unless the user explicitly asks for soft or hard enforcement.

Do not claim completion without proof.
Do not claim tests passed without command output.
Do not broaden scope.
Do not touch deploy, publish, sync, or release paths unless explicitly requested.
Do not treat docs-only changes as implementation proof.
Do not treat script existence as command execution proof.
Do not treat Codex-reported command output as strong local proof.
For visual/layout claims, collect or register screenshot proof with `stax:collect-visual`; do not make the user manually translate screenshots into prose proof.

Before final response, write or update:

```txt
.stax/codex-report.md
```

Required report:

- STAX acknowledgement
- Objective
- Files changed
- Tests added
- Commands run
- Command output summary with exit codes
- What is verified
- What is weak/provisional
- What is unverified
- Risks
- One next action
<!-- /STAX_PROJECT_CONTROL_PROTOCOL_V1 -->
