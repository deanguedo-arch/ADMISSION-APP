param(
  [string]$ConfigPath = ".\\config\\sheets_sync.json",
  [string]$IndexSourcePath = ".\\PROGRAMS_INDEX.csv",
  [string]$CleanIndexPath = ".\\pipeline\\program_index.cleaned.csv",
  [string]$CanonicalPath = ".\\data\\ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv",
  [string]$CanonicalFallbackPath = ".\\data\\ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv.new",
  [switch]$SkipValidation,
  [switch]$SkipRebuild,
  [switch]$SkipProgramUrlApply
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-CfgValue([object]$cfg, [string]$name, [object]$defaultValue = $null) {
  $prop = $cfg.PSObject.Properties[$name]
  if ($null -eq $prop) { return $defaultValue }
  if ($null -eq $prop.Value) { return $defaultValue }
  return $prop.Value
}

function Resolve-CanonicalPath([string]$canonicalPath, [string]$fallbackPath) {
  $canonicalExists = Test-Path $canonicalPath
  $fallbackExists = Test-Path $fallbackPath

  if ($canonicalExists -and $fallbackExists) {
    $a = Get-Item $canonicalPath
    $b = Get-Item $fallbackPath
    if ($b.LastWriteTimeUtc -gt $a.LastWriteTimeUtc) { return $fallbackPath }
    return $canonicalPath
  }
  if ($canonicalExists) { return $canonicalPath }
  if ($fallbackExists) { return $fallbackPath }
  throw "Could not find canonical CSV at $canonicalPath or $fallbackPath"
}

if (-not (Test-Path $ConfigPath)) {
  throw "Missing config: $ConfigPath. Copy config\\sheets_sync.json.example -> config\\sheets_sync.json and fill values."
}

$cfg = Get-Content $ConfigPath -Raw | ConvertFrom-Json
$webhook = [string](Get-CfgValue $cfg "webhook_url" "")
$token = [string](Get-CfgValue $cfg "sync_token" "")
$sheet = [string](Get-CfgValue $cfg "sheet_name" "Programs")
if ([string]::IsNullOrWhiteSpace($sheet)) { $sheet = "Programs" }

$minRowsRaw = Get-CfgValue $cfg "min_rows" 100
$maxDropRaw = Get-CfgValue $cfg "max_row_drop_percent" 35
$baselinePath = [string](Get-CfgValue $cfg "baseline_path" ".\\out\\last_good_programs.csv")
$requiredInstitutionsRaw = Get-CfgValue $cfg "required_institutions" @("NAIT", "NorQuest", "MacEwan", "UAlberta")

$minRows = [int]$minRowsRaw
if ($minRows -lt 1) { $minRows = 1 }

$maxRowDropPercent = [double]$maxDropRaw
if ($maxRowDropPercent -lt 0) { $maxRowDropPercent = 0 }

$requiredInstitutions = @($requiredInstitutionsRaw | ForEach-Object { [string]$_ } | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
if ($requiredInstitutions.Count -eq 0) {
  $requiredInstitutions = @("NAIT", "NorQuest", "MacEwan", "UAlberta")
}

if ([string]::IsNullOrWhiteSpace($webhook)) { throw "Config missing webhook_url in $ConfigPath" }
if ([string]::IsNullOrWhiteSpace($token)) { throw "Config missing sync_token in $ConfigPath" }

$python = ".\\.venv\\Scripts\\python.exe"
if (-not (Test-Path $python)) {
  throw "Missing venv python at $python. Run: .\\tools\\setup-python.ps1"
}

if (-not $SkipRebuild) {
  Write-Host "Rebuilding canonical dataset..."
  powershell -ExecutionPolicy Bypass -File .\\tools\\clean-master.ps1 | Out-Host
} else {
  Write-Host "Skipping canonical rebuild (-SkipRebuild)."
}

$activeCanonicalPath = Resolve-CanonicalPath -canonicalPath $CanonicalPath -fallbackPath $CanonicalFallbackPath
Write-Host "Active canonical path: $activeCanonicalPath"

if (-not $SkipProgramUrlApply) {
  Write-Host ""
  Write-Host "Refreshing program index and applying Program_URL mappings..."
  if (-not (Test-Path $IndexSourcePath)) {
    throw "Index source file not found: $IndexSourcePath"
  }

  & $python .\\pipeline\\build_norquest_seed_from_api.py
  if ($LASTEXITCODE -ne 0) {
    throw "Failed to refresh NorQuest seed (exit code $LASTEXITCODE)."
  }

  & $python .\\pipeline\\build_macewan_seed_from_element.py
  if ($LASTEXITCODE -ne 0) {
    throw "Failed to refresh MacEwan seed (exit code $LASTEXITCODE)."
  }

  & $python .\\pipeline\\build_ualberta_seed_from_coveo.py
  if ($LASTEXITCODE -ne 0) {
    throw "Failed to refresh UAlberta seed (exit code $LASTEXITCODE)."
  }

  & $python .\\pipeline\\build_index.py --in $IndexSourcePath --out $CleanIndexPath
  if ($LASTEXITCODE -ne 0) {
    throw "Failed to build cleaned index for URL mapping (exit code $LASTEXITCODE)."
  }

  $urlFallbackPath = "$activeCanonicalPath.next"
  & .\\tools\\apply-program-urls.ps1 `
    -IndexPath $CleanIndexPath `
    -CanonicalPath $activeCanonicalPath `
    -CanonicalFallbackPath $urlFallbackPath | Out-Host
  $activeCanonicalPath = Resolve-CanonicalPath -canonicalPath $activeCanonicalPath -fallbackPath $urlFallbackPath
  Write-Host "Active canonical path: $activeCanonicalPath"
} else {
  Write-Host "Skipping Program_URL apply (-SkipProgramUrlApply)."
}
$csvPath = $activeCanonicalPath

if (-not $SkipValidation) {
  Write-Host ""
  Write-Host "Running validation gate..."
  & .\\tools\\validate-canonical.ps1 `
    -CsvPath $csvPath `
    -BaselinePath $baselinePath `
    -MinRows $minRows `
    -MaxRowDropPercent $maxRowDropPercent `
    -RequiredInstitutions $requiredInstitutions | Out-Host
}

Write-Host ""
Write-Host "Uploading to Sheets tab '$sheet' from '$csvPath'..."
& $python .\\pipeline\\push_to_sheets.py --webhook $webhook --token $token --sheet $sheet --csv $csvPath

$baselineDir = Split-Path -Parent $baselinePath
if (-not (Test-Path $baselineDir)) {
  New-Item -ItemType Directory -Path $baselineDir | Out-Null
}
Copy-Item -LiteralPath $csvPath -Destination $baselinePath -Force

Write-Host ""
Write-Host "Done."
