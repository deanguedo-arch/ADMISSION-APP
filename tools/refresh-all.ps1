param(
  [string]$ConfigPath = ".\\config\\sheets_sync.json",
  [string]$IndexSourcePath = ".\\PROGRAMS_INDEX.csv",
  [string]$CleanIndexPath = ".\\pipeline\\program_index.cleaned.csv",
  [string]$ArtifactsOut = ".\\pipeline_artifacts",
  [int]$Limit = 0,
  [string[]]$Institution = @(),
  [switch]$SkipFixtures,
  [switch]$SkipScrape,
  [switch]$SkipAvgApply,
  [switch]$SkipProgramUrlApply,
  [switch]$SkipElectivePrefill,
  [switch]$SkipSync,
  [switch]$SkipValidation,
  [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..")
Set-Location $repoRoot

$python = ".\\.venv\\Scripts\\python.exe"
if (-not (Test-Path $python)) {
  throw "Missing venv python at $python. Run: .\\tools\\setup-python.ps1"
}

function Invoke-PythonChecked([string[]]$CommandArgs) {
  & $python @CommandArgs
  if ($LASTEXITCODE -ne 0) {
    throw "Python command failed (exit code $LASTEXITCODE): $($CommandArgs -join ' ')"
  }
}

if ($DryRun) {
  $SkipSync = $true
  Write-Host "DryRun enabled: sync/publish steps will be skipped."
}

Write-Host ""
Write-Host "Step 1/9: Rebuild canonical dataset"
& .\\tools\\clean-master.ps1 | Out-Host

Write-Host ""
Write-Host "Step 2/9: Build cleaned program index"
$buildArgs = @(".\\pipeline\\build_index.py", "--in", $IndexSourcePath, "--out", $CleanIndexPath)
foreach ($inst in @($Institution)) {
  if ([string]::IsNullOrWhiteSpace($inst)) { continue }
  $buildArgs += @("--institution", [string]$inst)
}
Invoke-PythonChecked $buildArgs

if (-not $SkipFixtures) {
  Write-Host ""
  Write-Host "Step 3/9: Run extractor/link fixture checks"
  Invoke-PythonChecked @(".\\pipeline\\check_avg_total_fixtures.py")
  Invoke-PythonChecked @(".\\pipeline\\check_enrichment_link_fixtures.py")
  Invoke-PythonChecked @(".\\pipeline\\check_nait_program_filter_fixtures.py")
} else {
  Write-Host ""
  Write-Host "Step 3/9: Skipped fixture checks (-SkipFixtures)"
}

if (-not $SkipScrape) {
  Write-Host ""
  Write-Host "Step 4/9: Run scrape/enrichment extraction"
  $runArgs = @(".\\pipeline\\run.py", "--index", $CleanIndexPath, "--out", $ArtifactsOut)
  if ($Limit -gt 0) {
    $runArgs += @("--limit", [string]$Limit)
  }
  foreach ($inst in @($Institution)) {
    if ([string]::IsNullOrWhiteSpace($inst)) { continue }
    $runArgs += @("--institution", [string]$inst)
  }
  Invoke-PythonChecked $runArgs
} else {
  Write-Host ""
  Write-Host "Step 4/9: Skipped scrape/enrichment extraction (-SkipScrape)"
}

$candidatesPath = Join-Path $ArtifactsOut "extract\\avg_total_candidates.csv"
if (-not $SkipAvgApply) {
  Write-Host ""
  Write-Host "Step 5/9: Apply Avg_Total candidates into canonical CSV"
  if (-not (Test-Path $candidatesPath)) {
    if ($SkipScrape) {
      Write-Host "Avg_Total candidates file not found after -SkipScrape; skipping Avg_Total apply."
    } else {
      throw "Avg_Total candidates file not found: $candidatesPath"
    }
  } elseif ($DryRun) {
    & .\\tools\\apply-avg-total-candidates.ps1 -CandidatesPath $candidatesPath -DryRun | Out-Host
  } else {
    & .\\tools\\apply-avg-total-candidates.ps1 -CandidatesPath $candidatesPath | Out-Host
  }
} else {
  Write-Host ""
  Write-Host "Step 5/9: Skipped Avg_Total apply (-SkipAvgApply)"
}

if (-not $SkipProgramUrlApply) {
  Write-Host ""
  Write-Host "Step 6/9: Apply Program_URL mappings into canonical CSV"
  if (-not (Test-Path $CleanIndexPath)) {
    throw "Clean index file not found: $CleanIndexPath"
  } elseif ($DryRun) {
    & .\\tools\\apply-program-urls.ps1 -IndexPath $CleanIndexPath -DryRun | Out-Host
  } else {
    & .\\tools\\apply-program-urls.ps1 -IndexPath $CleanIndexPath | Out-Host
  }
} else {
  Write-Host ""
  Write-Host "Step 6/9: Skipped Program_URL apply (-SkipProgramUrlApply)"
}

Write-Host ""
Write-Host "Step 7/9: Regenerate ElectiveRules todo template"
& .\\tools\\generate-elective-rules-template.ps1 | Out-Host

if (-not $SkipElectivePrefill) {
  Write-Host ""
  Write-Host "Step 8/9: Prefill ElectiveRules suggestions"
  Invoke-PythonChecked @(".\\tools\\prefill-elective-rules.py")
} else {
  Write-Host ""
  Write-Host "Step 8/9: Skipped ElectiveRules prefill (-SkipElectivePrefill)"
}

if (-not $SkipSync) {
  Write-Host ""
  Write-Host "Step 9/9: Sync Programs + ElectiveRules to Google Sheets"
  if ($SkipValidation) {
    & .\\tools\\sync-programs.ps1 -ConfigPath $ConfigPath -SkipRebuild -SkipValidation | Out-Host
  } else {
    & .\\tools\\sync-programs.ps1 -ConfigPath $ConfigPath -SkipRebuild | Out-Host
  }
  & .\\tools\\sync-elective-rules.ps1 -ConfigPath $ConfigPath | Out-Host
} else {
  Write-Host ""
  Write-Host "Step 9/9: Skipped Google Sheets sync (-SkipSync)"
}

Write-Host ""
Write-Host "Refresh flow completed."
