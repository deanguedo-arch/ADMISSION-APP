# Offline Snapshot (Standalone, Frozen)

This folder builds a standalone website snapshot of the admissions checker with:

- no Apps Script runtime dependency
- no Google Sheets dependency at runtime
- frozen admissions dataset from canonical CSV at build time

## Build

From repo root:

```powershell
.\BUILD_OFFLINE_SNAPSHOT.bat
```

or:

```powershell
.\.venv\Scripts\python.exe .\offline_snapshot\build_snapshot.py
```

## Local Preview

Double-click:

- `START_OFFLINE_SNAPSHOT_PREVIEW.bat`

Note: this launcher now rebuilds the snapshot first, then starts preview (`update -> preview`).

Or run:

```powershell
.\offline_snapshot\start-preview.ps1 -Mode auto -Port 5180 -OpenBrowser
```

## Output

Generated site files are written to:

- `offline_snapshot/site/index.html`
- `offline_snapshot/site/runtime/eligibility_core.js`
- `offline_snapshot/site/runtime/offline_bridge.js`
- `offline_snapshot/site/data/snapshot_data.js`
- `offline_snapshot/site/snapshot.meta.json`

## Deploy

Upload the contents of `offline_snapshot/site/` to any static web host and link users to `index.html`.

GitHub Pages one-action deployment:
- Run workflow: `Update + Build + Deploy Offline Snapshot (GitHub Pages)`
- It performs `refresh -> build -> deploy` in a single run.

## Optional Snapshot Inputs

If you want fixed override behavior in the snapshot, provide optional CSVs before building:

- `offline_snapshot/input/AvgRules.csv`
- `offline_snapshot/input/ElectiveRules.csv`

If omitted, snapshot uses only the canonical dataset values.
