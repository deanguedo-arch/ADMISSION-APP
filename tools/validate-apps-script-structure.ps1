param(
  [string]$AppsScriptDir = "apps_script",
  [switch]$WarnOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$issues = New-Object System.Collections.Generic.List[string]

function Add-Issue([string]$msg) {
  $script:issues.Add($msg)
}

function Get-TopLevelFunctions([string]$path) {
  if (-not (Test-Path -LiteralPath $path)) {
    return @()
  }
  $code = Get-Content -LiteralPath $path -Raw
  $matches = [regex]::Matches($code, '(?m)^function\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(')
  $out = @()
  foreach ($m in $matches) {
    $out += $m.Groups[1].Value
  }
  return $out
}

if (-not (Test-Path -LiteralPath $AppsScriptDir)) {
  throw "Apps Script directory not found: $AppsScriptDir"
}

$expectedByFile = @{
  "Code.gs" = @(
    "onOpen",
    "onEdit",
    "autoFillManualElectiveGroupsFromEdit_",
    "autoFillManualElectiveGroupRow_",
    "runEligibility_",
    "doGet",
    "getWebAppBootstrapData",
    "runWebEligibility",
    "getAdmissionsSpreadsheet_"
  )
  "WebAuth.gs" = @(
    "getWebAppClientConfig_",
    "getWebAppAllowedGoogleClientIds_",
    "sanitizeWebPayload_",
    "sanitizeWebAuthPayload_",
    "assertAllowedObjectKeys_",
    "assertAuthorizedWebUser_",
    "verifyGoogleIdToken_",
    "assertDomainUser_",
    "assertWebRateLimit_",
    "sanitizeWebMessage_",
    "listNamedCourseOptions_",
    "sanitizeWebNamedCourses_",
    "sanitizeWebManualElectives_",
    "buildWebAllowedCourseSet_",
    "copyWebDetailsByKey_"
  )
  "WorkbookAdmin.gs" = @(
    "setupWorkbookForStaff_",
    "ensureSheet_",
    "isStaffEditableSheet_",
    "isQuietSetup_",
    "assertAdminRunner_",
    "removeManagedSheetProtection_",
    "ensureManagedSheetProtection_",
    "applyStaffLockdown_",
    "adminShowAllTabs_",
    "setupStudentElectiveInputs_",
    "setupElectiveRulesTemplate_",
    "notifyStudentSetupComplete_"
  )
}

foreach ($fileName in $expectedByFile.Keys) {
  $path = Join-Path $AppsScriptDir $fileName
  if (-not (Test-Path -LiteralPath $path)) {
    Add-Issue("Missing expected module file: $fileName")
    continue
  }

  $actual = Get-TopLevelFunctions -path $path
  $expected = $expectedByFile[$fileName]

  $missing = @($expected | Where-Object { $actual -notcontains $_ })
  if ($missing.Count -gt 0) {
    Add-Issue("$fileName missing expected functions: $($missing -join ', ')")
  }

  $extra = @($actual | Where-Object { $expected -notcontains $_ })
  if ($extra.Count -gt 0) {
    Add-Issue("$fileName contains unexpected functions: $($extra -join ', ')")
  }
}

$engineFile = Join-Path $AppsScriptDir "EligibilityEngine.gs"
if (-not (Test-Path -LiteralPath $engineFile)) {
  Add-Issue("Missing expected module file: EligibilityEngine.gs")
} else {
  $engineFns = Get-TopLevelFunctions -path $engineFile
  $engineRequired = @(
    "evaluateProgramsForStudent_",
    "readAvgRules_",
    "readElectiveRuleOverrides_",
    "buildCourseMap_",
    "computeStudentAverage_",
    "parseElectiveRules_"
  )
  $engineMissing = @($engineRequired | Where-Object { $engineFns -notcontains $_ })
  if ($engineMissing.Count -gt 0) {
    Add-Issue("EligibilityEngine.gs missing required core functions: $($engineMissing -join ', ')")
  }

  $enginePublic = @($engineFns | Where-Object { -not $_.EndsWith("_") })
  if ($enginePublic.Count -gt 0) {
    Add-Issue("EligibilityEngine.gs should not expose public top-level functions: $($enginePublic -join ', ')")
  }
}

if ($issues.Count -gt 0) {
  Write-Host ""
  Write-Host "validate-apps-script-structure: FAIL" -ForegroundColor Red
  foreach ($issue in $issues) {
    Write-Host (" - " + $issue) -ForegroundColor Red
  }
  if (-not $WarnOnly) {
    exit 1
  }
  Write-Host ""
  Write-Host "WarnOnly enabled; exiting 0." -ForegroundColor Yellow
  exit 0
}

Write-Host ""
Write-Host "validate-apps-script-structure: PASS" -ForegroundColor Green
Write-Host (" - Apps Script dir: " + $AppsScriptDir)
Write-Host (" - Checked shell modules: " + (($expectedByFile.Keys | Sort-Object) -join ", "))
Write-Host " - Checked EligibilityEngine core function set and public surface"
exit 0
