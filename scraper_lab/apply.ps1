param(
  [string]$CycleId = "",
  [string]$RunScope = "canonical334",
  [string]$CandidatesPath = "",
  [string]$IssuePackPath = ".\scraper_lab\issue_pack.csv",
  [string]$CanonicalPath = ".\data\ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv",
  [string]$CanonicalFallbackPath = ".\data\ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv.new",
  [string[]]$AllowedConfidence = @("high", "medium"),
  [switch]$IncludeLowConfidence,
  [switch]$AllowOverwriteExisting,
  [string]$Profile = "candidate",
  [switch]$Apply
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Resolve-LatestCyclePath([string]$runsRoot) {
  if (-not (Test-Path $runsRoot)) {
    throw "Runs folder not found: $runsRoot. Run .\scraper_lab\run.ps1 first."
  }
  $latest = Get-ChildItem -Path $runsRoot -Directory |
    Sort-Object LastWriteTimeUtc -Descending |
    Select-Object -First 1
  if ($null -eq $latest) {
    throw "No lab cycles found in $runsRoot. Run .\scraper_lab\run.ps1 first."
  }
  return $latest.FullName
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..")
Set-Location $repoRoot

$runsRoot = Join-Path $repoRoot "scraper_lab\runs"
if (-not $CandidatesPath) {
  $cycleRoot = if ($CycleId) {
    Join-Path $runsRoot $CycleId
  } else {
    Resolve-LatestCyclePath -runsRoot $runsRoot
  }
  $scopePath = if ((Test-Path (Join-Path $cycleRoot $RunScope))) {
    Join-Path $cycleRoot $RunScope
  } else {
    $cycleRoot
  }
  $CandidatesPath = Join-Path $scopePath "candidate\extract\program_field_candidates.csv"
}

if (-not (Test-Path $CandidatesPath)) {
  throw "Candidate file not found: $CandidatesPath"
}

$applyToolPath = Join-Path $repoRoot "tools\apply-program-field-candidates.ps1"
$applyParams = @{
  CandidatesPath = $CandidatesPath
  CanonicalPath = $CanonicalPath
  CanonicalFallbackPath = $CanonicalFallbackPath
  IssuePackPath = $IssuePackPath
  AllowedConfidence = @($AllowedConfidence)
  Profile = $Profile
}
if ($IncludeLowConfidence) { $applyParams.IncludeLowConfidence = $true }
if ($AllowOverwriteExisting) { $applyParams.AllowOverwriteExisting = $true }
if (-not $Apply) {
  Write-Host "Dry-run mode (default). Use -Apply to write changes."
  $applyParams.DryRun = $true
}

& $applyToolPath @applyParams
if (-not $?) {
  throw "Apply step failed."
}
