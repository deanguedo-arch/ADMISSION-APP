param(
  [string]$CycleId = "",
  [string]$RunScope = "canonical334",
  [string]$IndexSourcePath = ".\PROGRAMS_INDEX.csv",
  [string]$ProgramOverridesPath = ".\data\PROGRAM_OVERRIDES.csv",
  [int]$Limit = 0,
  [string[]]$Institution = @("NAIT", "NorQuest", "MacEwan", "UAlberta"),
  [switch]$ReuseFrozenFetch,
  [switch]$SkipFixtures,
  [switch]$SkipCompare,
  [switch]$AllowUnsafeMain
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..")
Set-Location $repoRoot

$labRoot = Join-Path $repoRoot "scraper_lab"
$issuePackPath = Join-Path $labRoot "issue_pack.csv"
$issuePackTemplate = Join-Path $repoRoot "docs\templates\scraper_issue_pack.template.csv"

if (-not (Test-Path $issuePackPath)) {
  if (Test-Path $issuePackTemplate) {
    Copy-Item -Force $issuePackTemplate $issuePackPath
    Write-Host "Seeded issue pack: $issuePackPath"
  } else {
    throw "Missing issue pack template: $issuePackTemplate"
  }
}

$runnerPath = Join-Path $repoRoot "tools\run-scraper-lab-cycle.ps1"
$runnerParams = @{
  RunScope = $RunScope
  IndexSourcePath = $IndexSourcePath
  ProgramOverridesPath = $ProgramOverridesPath
  Limit = $Limit
  Institution = ($Institution -join ",")
  RunsRoot = (Join-Path $labRoot "runs")
  IssuePackPath = $issuePackPath
}
if ($CycleId) { $runnerParams.CycleId = $CycleId }
if ($ReuseFrozenFetch) { $runnerParams.ReuseFrozenFetch = $true }
if ($SkipFixtures) { $runnerParams.SkipFixtures = $true }
if ($SkipCompare) { $runnerParams.SkipCompare = $true }
if ($AllowUnsafeMain) { $runnerParams.AllowUnsafeMain = $true }

& $runnerPath @runnerParams
if (-not $?) {
  throw "Lab cycle failed."
}
