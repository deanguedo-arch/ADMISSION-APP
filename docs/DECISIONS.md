# Architecture Decisions

This file is the stable decision source for future sessions. Update it only when a decision changes.

## ADR-001: Web App Access Model
- Date: 2026-02-10
- Status: Active
- Decisions:
  - Web app deployment access is `ANYONE` (Google sign-in required; not anonymous).
  - Allowed identity domain is `@eips.ca`.
  - Non-domain users are not supported.
  - Web app remains `executeAs: USER_DEPLOYING` for now.
  - Web access is enforced by Google ID token validation (audience allowlist + verified email + hosted domain).
  - Public web-callable backend surface is limited to:
    - `doGet`
    - `getWebAppBootstrapData`
    - `runWebEligibility`

## ADR-002: Truth Model
- Date: 2026-02-10
- Status: Active
- Decisions:
  - `Programs` (+ optional `AvgRules`, `ElectiveRules`) in Sheets is the live truth used by sheet runs and web runs.
  - Web app student input is request-scoped and not persisted by default.
  - Canonical dataset source remains `data/ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv` for refresh/publish workflows.

## ADR-003: Security Boundary for Sync
- Date: 2026-02-10
- Status: Target
- Decisions:
  - Preferred target is separating sync webhook logic into a dedicated Apps Script project.
  - Admissions web app project should avoid exposing webhook/admin surfaces.

## ADR-004: Delivery Workflow
- Date: 2026-02-10
- Status: Active
- Decisions:
  - Ship in small slices: security -> backend response -> UI -> export/performance/ops.
  - One slice per commit.
  - Run `tools/validate-webapp-surface.ps1` before web app pushes.
