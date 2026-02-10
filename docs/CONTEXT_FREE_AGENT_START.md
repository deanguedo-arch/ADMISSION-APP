# Context-Free Agent Start

Use this in a brand-new chat.

## Copy/Paste Prompt
You are joining this project with no prior chat context.  
Read these files first, in order:
1. `docs/SESSION_HANDOFF.md`
2. `docs/SPRINT_SLICE.md`
3. `docs/PROJECT_CONTEXT.md`
4. `docs/WORK_LOG.md`

Then execute the next list with narrow, surgical changes only:
1. Run baseline guardrails and report results:
   - `tools/validate-webapp-surface.ps1`
   - `tools/validate-apps-script-structure.ps1`
2. Complete Sprint Slice 4: performance + lightweight audit hardening.
3. Complete Sprint Slice 5: deployed/manual QA from `docs/WEBAPP_QA_CHECKLIST.md`.
4. Produce release-ready handoff:
   - update `docs/WORK_LOG.md`
   - run `tools/handoff.ps1`
   - summarize risks, rollback point, and exact next seam.

Constraints:
- Preserve behavior unless a bug fix is explicitly required.
- One seam per commit.
- Keep callable Apps Script surface minimal.
- Re-run validators after each seam.

Required output each seam:
- Plan
- Files touched and why
- Validation run results
- Risks and rollback
- Next seam recommendation
