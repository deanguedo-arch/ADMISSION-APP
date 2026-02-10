# Manual Apps Script Export

If you need to paste code into another Apps Script project manually, use the export tool to generate one-file bundles.

## Command

```powershell
.\tools\export-appsscript-bundles.ps1 -Profile all
```

Outputs are written to `out/exports/`:

- `Code.bundle.full.gs` (Admissions checker code, including web app backend functions)
- `Code.bundle.sheet-only.gs` (Admissions checker code without web app endpoint/auth functions)
- `Code.bundle.sync-only.gs` (Sync webhook code from `SyncPrograms.gs`)

## Common usage

Sheet-only destination (no web app backend):

```powershell
.\tools\export-appsscript-bundles.ps1 -Profile sheet-only
```

Generate one bundle and copy it directly to clipboard:

```powershell
.\tools\export-appsscript-bundles.ps1 -Profile sheet-only -CopyToClipboard
```

Sync webhook only:

```powershell
.\tools\export-appsscript-bundles.ps1 -Profile sync-only
```

## Notes

- The tool is safe to run repeatedly; outputs are overwritten.
- Generated files include a header with profile + timestamp + source file list.
- `sheet-only` is intended for projects that do not use the web app endpoint/auth surface.
