param(
  [string]$CycleId = "",
  [string]$RunScope = "canonical334",
  [string]$IndexSourcePath = ".\PROGRAMS_INDEX.csv",
  [string]$ProgramOverridesPath = ".\data\PROGRAM_OVERRIDES.csv",
  [string]$CanonicalPath = ".\data\ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv",
  [string]$CanonicalFallbackPath = ".\data\ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv.new",
  [string]$RunsRoot = ".\scraper_lab\runs",
  [string]$IssuePackPath = ".\scraper_lab\issue_pack.csv",
  [int]$Limit = 0,
  [string[]]$Institution = @("NAIT", "NorQuest", "MacEwan", "UAlberta"),
  [switch]$ReuseFrozenFetch,
  [switch]$SkipFixtures,
  [switch]$SkipCompare,
  [switch]$AllowUnsafeMain,
  [switch]$AllowApply,
  [switch]$AllowSync,
  [switch]$AllowDeploy
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Invoke-GitChecked([string[]]$CmdArgs) {
  $result = & git @CmdArgs
  if ($LASTEXITCODE -ne 0) {
    throw "git $($CmdArgs -join ' ') failed with exit code $LASTEXITCODE"
  }
  return $result
}

function Invoke-PythonChecked([string[]]$CmdArgs, [string]$PythonExe) {
  & $PythonExe @CmdArgs
  if ($LASTEXITCODE -ne 0) {
    throw "Python command failed (exit code $LASTEXITCODE): $($CmdArgs -join ' ')"
  }
}

function Expand-Institutions([string[]]$Values) {
  $expanded = @()
  foreach ($value in @($Values)) {
    if ([string]::IsNullOrWhiteSpace($value)) { continue }
    $parts = ($value -split "[,\s]+" | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    foreach ($part in $parts) {
      $expanded += $part.Trim()
    }
  }
  return ,$expanded
}

function Resolve-RunScopes([string]$Requested) {
  if ([string]::IsNullOrWhiteSpace($Requested)) {
    $normalized = "canonical334"
  } else {
    $normalized = $Requested.Trim().ToLowerInvariant()
  }
  switch ($normalized) {
    "canonical334" { return @("canonical334") }
    "filtered220" { return @("filtered220") }
    "both" { return @("canonical334", "filtered220") }
    default { throw "Invalid -RunScope '$Requested'. Expected canonical334, filtered220, or both." }
  }
}

function Resolve-ScopedRoot([string]$CycleRoot, [string]$ScopeName, [bool]$UseSubfolders) {
  if ($UseSubfolders) {
    return Join-Path $CycleRoot $ScopeName
  }
  return $CycleRoot
}

function Get-ExpectedRows([string]$IndexPath, [int]$LimitValue) {
  if (-not (Test-Path $IndexPath)) { return 0 }
  $rows = @(Import-Csv $IndexPath)
  $count = $rows.Count
  if ($LimitValue -gt 0 -and $LimitValue -lt $count) {
    return $LimitValue
  }
  return $count
}

function Build-ScopedIndex(
  [string]$ScopeName,
  [string]$IndexOut,
  [string]$RelevanceOut,
  [string[]]$Institutions,
  [string]$PythonExe,
  [string]$CanonicalCsv,
  [string]$CanonicalFallbackCsv,
  [string]$SourceIndexPath,
  [string]$OverridesPath
) {
  if ($ScopeName -eq "canonical334") {
    $buildArgs = @(
      ".\pipeline\build_canonical_index.py",
      "--canonical", $CanonicalCsv,
      "--canonical-fallback", $CanonicalFallbackCsv,
      "--out", $IndexOut
    )
    foreach ($inst in @($Institutions)) {
      if ([string]::IsNullOrWhiteSpace($inst)) { continue }
      $buildArgs += @("--institution", [string]$inst)
    }
    Invoke-PythonChecked -CmdArgs $buildArgs -PythonExe $PythonExe
    return
  }

  $buildArgs = @(
    ".\pipeline\build_index.py",
    "--in", $SourceIndexPath,
    "--out", $IndexOut,
    "--relevance-out", $RelevanceOut,
    "--program-overrides", $OverridesPath
  )
  foreach ($inst in @($Institutions)) {
    if ([string]::IsNullOrWhiteSpace($inst)) { continue }
    $buildArgs += @("--institution", [string]$inst)
  }
  Invoke-PythonChecked -CmdArgs $buildArgs -PythonExe $PythonExe
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..")
Set-Location $repoRoot

if ($AllowApply -or $AllowSync -or $AllowDeploy) {
  throw "run-scraper-lab-cycle.ps1 is lab-only and refuses apply/sync/deploy actions. Use dedicated publish scripts on approved promotion runs."
}

$branch = (Invoke-GitChecked -CmdArgs @("rev-parse", "--abbrev-ref", "HEAD") | Select-Object -First 1).Trim()
if (($branch -eq "main") -and (-not $AllowUnsafeMain)) {
  throw "Refusing to run on 'main'. Switch to scraper-lab (or pass -AllowUnsafeMain explicitly)."
}

if ([string]::IsNullOrWhiteSpace($CycleId)) {
  $CycleId = Get-Date -Format "yyyyMMdd-HHmmss"
}

$scopes = @(Resolve-RunScopes -Requested $RunScope)
$useScopeSubfolders = ($scopes.Count -gt 1)

$resolvedRunsRoot = if ([System.IO.Path]::IsPathRooted($RunsRoot)) {
  $RunsRoot
} else {
  Join-Path $repoRoot $RunsRoot
}
$resolvedIssuePackPath = if ([System.IO.Path]::IsPathRooted($IssuePackPath)) {
  $IssuePackPath
} else {
  Join-Path $repoRoot $IssuePackPath
}
$issuePackDir = Split-Path -Parent $resolvedIssuePackPath
if (-not (Test-Path $issuePackDir)) {
  New-Item -ItemType Directory -Force -Path $issuePackDir | Out-Null
}
if (-not (Test-Path $resolvedIssuePackPath)) {
  $template = Join-Path $repoRoot "docs\templates\scraper_issue_pack.template.csv"
  if (Test-Path $template) {
    Copy-Item -Force $template $resolvedIssuePackPath
  } else {
    "issue_id,canonical_row_id,institution,program,credential,program_url,issue_type,field_name,expected_value,actual_value,evidence_url,evidence_snippet,severity,status,approval_state,approved_by,approved_at,notes" | Out-File -FilePath $resolvedIssuePackPath -Encoding utf8
  }
}

$python = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
  throw "Missing venv python at $python. Run: .\tools\setup-python.ps1"
}

$cycleRoot = Join-Path $resolvedRunsRoot $CycleId
$institutionFilters = Expand-Institutions -Values $Institution

Write-Host ""
Write-Host "=== Scraper Lab Cycle ==="
Write-Host "Branch: $branch"
Write-Host "Cycle: $CycleId"
Write-Host "Run scope: $RunScope"
Write-Host "Runs root: $resolvedRunsRoot"
Write-Host "Cycle root: $cycleRoot"
Write-Host "Institutions: $($institutionFilters -join ', ')"
Write-Host "Issue pack: $resolvedIssuePackPath"

New-Item -ItemType Directory -Force -Path $resolvedRunsRoot, $cycleRoot | Out-Null

# Step 1: Build scoped indexes first.
foreach ($scope in $scopes) {
  $scopeRoot = Resolve-ScopedRoot -CycleRoot $cycleRoot -ScopeName $scope -UseSubfolders:$useScopeSubfolders
  $indexRoot = Join-Path $scopeRoot "index"
  $indexOut = Join-Path $indexRoot ("program_index.{0}.csv" -f $scope)
  $relevanceOut = Join-Path $indexRoot "relevance_decisions.csv"
  New-Item -ItemType Directory -Force -Path $scopeRoot, $indexRoot | Out-Null

  Write-Host ""
  Write-Host "Step 1: Build index for scope '$scope'"
  Build-ScopedIndex `
    -ScopeName $scope `
    -IndexOut $indexOut `
    -RelevanceOut $relevanceOut `
    -Institutions $institutionFilters `
    -PythonExe $python `
    -CanonicalCsv $CanonicalPath `
    -CanonicalFallbackCsv $CanonicalFallbackPath `
    -SourceIndexPath $IndexSourcePath `
    -OverridesPath $ProgramOverridesPath
}

if (-not $SkipFixtures) {
  Write-Host ""
  Write-Host "Step 2: Run scraper fixtures"
  Invoke-PythonChecked -CmdArgs @(".\pipeline\check_avg_total_fixtures.py") -PythonExe $python
  Invoke-PythonChecked -CmdArgs @(".\pipeline\check_enrichment_link_fixtures.py") -PythonExe $python
  Invoke-PythonChecked -CmdArgs @(".\pipeline\check_nait_program_filter_fixtures.py") -PythonExe $python
  Invoke-PythonChecked -CmdArgs @(".\pipeline\check_macewan_seed_fixtures.py") -PythonExe $python
  Invoke-PythonChecked -CmdArgs @(".\pipeline\check_ualberta_url_map_fixtures.py") -PythonExe $python
  Invoke-PythonChecked -CmdArgs @(".\pipeline\check_program_field_fixtures.py") -PythonExe $python
} else {
  Write-Host ""
  Write-Host "Step 2: Skipped fixtures (-SkipFixtures)"
}

$scopeSummaries = @()
$anyGateFailed = $false
foreach ($scope in $scopes) {
  $scopeRoot = Resolve-ScopedRoot -CycleRoot $cycleRoot -ScopeName $scope -UseSubfolders:$useScopeSubfolders
  $indexRoot = Join-Path $scopeRoot "index"
  $fetchRoot = Join-Path $scopeRoot "fetch_frozen"
  $baselineOut = Join-Path $scopeRoot "baseline"
  $candidateOut = Join-Path $scopeRoot "candidate"
  $diffOut = Join-Path $scopeRoot "diff"
  $indexOut = Join-Path $indexRoot ("program_index.{0}.csv" -f $scope)
  $relevanceOut = Join-Path $indexRoot "relevance_decisions.csv"

  New-Item -ItemType Directory -Force -Path $fetchRoot, $baselineOut, $candidateOut, $diffOut | Out-Null
  $expectedRows = Get-ExpectedRows -IndexPath $indexOut -LimitValue $Limit

  Write-Host ""
  Write-Host "Step 3: Run baseline extraction for scope '$scope'"
  $baselineArgs = @(
    ".\pipeline\run.py",
    "--index", $indexOut,
    "--out", $baselineOut,
    "--profile", "baseline",
    "--fetch-dir", $fetchRoot
  )
  if ($ReuseFrozenFetch) {
    $baselineArgs += "--extract-only"
  }
  if ($Limit -gt 0) {
    $baselineArgs += @("--limit", [string]$Limit)
  }
  foreach ($inst in @($institutionFilters)) {
    if ([string]::IsNullOrWhiteSpace($inst)) { continue }
    $baselineArgs += @("--institution", [string]$inst)
  }
  Invoke-PythonChecked -CmdArgs $baselineArgs -PythonExe $python

  Write-Host ""
  Write-Host "Step 4: Run candidate extraction for scope '$scope' (extract-only from frozen fetch)"
  $candidateArgs = @(
    ".\pipeline\run.py",
    "--index", $indexOut,
    "--out", $candidateOut,
    "--profile", "candidate",
    "--fetch-dir", $fetchRoot,
    "--extract-only"
  )
  if ($Limit -gt 0) {
    $candidateArgs += @("--limit", [string]$Limit)
  }
  foreach ($inst in @($institutionFilters)) {
    if ([string]::IsNullOrWhiteSpace($inst)) { continue }
    $candidateArgs += @("--institution", [string]$inst)
  }
  Invoke-PythonChecked -CmdArgs $candidateArgs -PythonExe $python

  if (-not $SkipCompare) {
    $scopeGateStatus = "PASS"
    Write-Host ""
    Write-Host "Step 5: Compare baseline vs candidate and run gate for scope '$scope'"
    $compareArgs = @(
      ".\tools\compare-scraper-runs.py",
      "--baseline", (Join-Path $baselineOut "extract\program_field_candidates.csv"),
      "--candidate", (Join-Path $candidateOut "extract\program_field_candidates.csv"),
      "--issue-pack", $resolvedIssuePackPath,
      "--expected-baseline-rows", [string]$expectedRows,
      "--expected-candidate-rows", [string]$expectedRows,
      "--out-dir", $diffOut,
      "--strict"
    )
    if (Test-Path $relevanceOut) {
      $compareArgs += @("--baseline-relevance", $relevanceOut, "--candidate-relevance", $relevanceOut)
    }
    try {
      Invoke-PythonChecked -CmdArgs $compareArgs -PythonExe $python
    } catch {
      $scopeGateStatus = "FAIL"
      $anyGateFailed = $true
      Write-Warning "Gate failed for scope '$scope'. Continuing so Step 6 artifacts are still generated."
      Write-Warning $_
    }

    Write-Host ""
    Write-Host "Step 6: Build original-vs-new compare for scope '$scope'"
    $originalVsNewArgs = @(
      ".\tools\compare-original-vs-candidate.py",
      "--canonical", $CanonicalPath,
      "--canonical-fallback", $CanonicalFallbackPath,
      "--candidate", (Join-Path $candidateOut "extract\program_field_candidates.csv"),
      "--index", $indexOut,
      "--out-dir", $diffOut
    )
    if (Test-Path $relevanceOut) {
      $originalVsNewArgs += @("--relevance", $relevanceOut)
    }
    Invoke-PythonChecked -CmdArgs $originalVsNewArgs -PythonExe $python
  } else {
    $scopeGateStatus = "SKIPPED"
    Write-Host ""
    Write-Host "Step 5: Skipped compare gate for scope '$scope' (-SkipCompare)"
    Write-Host "Step 6: Skipped original-vs-new compare for scope '$scope'"
  }

  $scopeSummaries += [pscustomobject]@{
    Scope = $scope
    ScopeRoot = $scopeRoot
    Baseline = (Join-Path $baselineOut "extract\program_field_candidates.csv")
    Candidate = (Join-Path $candidateOut "extract\program_field_candidates.csv")
    GateReport = (Join-Path $diffOut "gate_report.md")
    GateStatus = $scopeGateStatus
    OriginalVsNew = (Join-Path $diffOut "original_vs_new_summary.md")
  }
}

Write-Host ""
Write-Host "Lab cycle complete."
foreach ($summary in $scopeSummaries) {
  Write-Host ""
  Write-Host "Scope: $($summary.Scope)"
  Write-Host "  Root: $($summary.ScopeRoot)"
  Write-Host "  Baseline fields: $($summary.Baseline)"
  Write-Host "  Candidate fields: $($summary.Candidate)"
  Write-Host "  Gate report: $($summary.GateReport)"
  Write-Host "  Gate status: $($summary.GateStatus)"
  Write-Host "  Original vs new summary: $($summary.OriginalVsNew)"
}

if ($anyGateFailed) {
  Write-Warning "One or more scopes failed the compare gate. Review gate_report.md and original_vs_new_* outputs."
}
