## Repo Proof Surface Candidate

Repo: ADMISSION-APP
Confidence: high
Status: candidate

## Detected Stack
- html-css
- node
- python

## Detected Proof Commands
- BUILD_OFFLINE_SNAPSHOT.bat
- START_OFFLINE_SNAPSHOT_PREVIEW.bat
- npm run build:pages
- tools/build-pages.js
- tools/build-review-queue.py
- tools/check-admission-route-display.js
- tools/check-audit-canonical-regressions.py
- tools/check-course-input-upsert.js
- tools/check-dataset-quality-fixtures.py
- tools/check-details-panel-height-sync.js
- tools/check-eligibility.ps1
- tools/check-explorer-program-structure.js
- tools/check-first-load-ux.js
- tools/check-high-school-display-flag.py
- tools/check-offline-bridge-explorer-bootstrap.js
- tools/check-placement-confidence.js
- tools/check-refresh-workflow-no-skip-scrape.js
- tools/check-release-gate-smoke.js
- tools/check-science-requirement-parsing.js
- tools/check-web-auth-bootstrap.js
- tools/check-web-high-school-filter.js
- tools/check-workspace.ps1
- tools/test-release-gate-smoke.js
- tools/validate-apps-script-structure.ps1
- tools/validate-canonical.ps1
- tools/validate-dataset.py
- tools/validate-sync-surface.ps1
- tools/validate-webapp-surface.ps1

## Detected Risky Actions
- PUBLISH_DATA_TO_SHEETS.bat requires explicit human approval, non-mutating preflight proof, target validation
- SYNC_ALL.cmd requires explicit human approval, non-mutating preflight proof, target validation
- SYNC_ELECTIVE_RULES.cmd requires explicit human approval, non-mutating preflight proof, target validation
- SYNC_PROGRAMS.cmd requires explicit human approval, non-mutating preflight proof, target validation
- scripts/SYNC_ALL.cmd requires explicit human approval, non-mutating preflight proof, target validation
- tools/setup-appsscript-deploy.ps1 requires explicit human approval, non-mutating preflight proof, target validation
- tools/sync-all-to-sheets.ps1 requires explicit human approval, non-mutating preflight proof, target validation
- tools/sync-elective-rules.ps1 requires explicit human approval, non-mutating preflight proof, target validation
- tools/sync-main.ps1 requires explicit human approval, non-mutating preflight proof, target validation
- tools/sync-programs.ps1 requires explicit human approval, non-mutating preflight proof, target validation

## Proposed Proof Rules
- build_ready: require local_command_output, target_repo_cwd (package.json scripts)
- tests_passed: require local_command_output, target_repo_cwd (package.json scripts)
- visual_ready: require rendered_screenshot, visual_checklist (workspace/config/script detection)
- publish_sync_deploy_ready: require human_approval, non_mutating_preflight, target_validation (risky package script detection)
- data_pipeline_ready: require schema_or_fixture_validation, quality_command_output (data script/path detection)
- gold_fixture_update: require source_truth_reference, separate_human_approval, validation_command_output (gold/fixture script or path detection)
- repo_identity: require target_repo_cwd, matching_repo_path, matching_worktree_fingerprint (generic STAX sidecar rule)

## Unknowns
- No unknowns recorded.

## Decision Needed
Approve this proof surface, edit it, or keep it candidate-only.
