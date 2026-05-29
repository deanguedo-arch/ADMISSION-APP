STAX Sidecar rejected or held this task because proof is incomplete.

Do exactly one cleanup pass:
Approved proof surface for build_ready: Run npm run build:pages through stax:collect in the target repo. Suggested command: npm run build:pages.

Address these proof gaps:
- Command evidence provenance is not verified for npm run build:pages -- --output /tmp/stax-admission-pages/index.html: wrong_commit.
- Command evidence freshness failed for npm run build:pages -- --output /tmp/stax-admission-pages/index.html: wrong_commit.
- Command evidence provenance is not verified for npm run build:pages: wrong_commit.
- Command evidence freshness failed for npm run build:pages: wrong_commit.
- STAX acknowledgement is stale or does not match the current turn contract.

Do not broaden scope. Do not claim tests passed without local command evidence. Update .stax/codex-report.md, then stop.
Risk to avoid: Command evidence risk: human-pasted output is not local STAX command evidence.
