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
    "includeHtml_",
    "getWebAppBootstrapData",
    "runWebEligibility",
    "getAdmissionsSpreadsheet_"
  )
  "WebAppRender.gs" = @(
    "renderWebAppHtml_",
    "readWebAppHtmlFile_",
    "resolveWebAppHtmlIncludes_"
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
    "generateProgramComparisonSheetFromPinned_",
    "buildUniqueSheetName_",
    "buildKeyRequirementsForComparisonRow_",
    "buildWhyFlagsForComparisonRow_",
    "formatSnapshotResultForComparison_",
    "nextActionForConfidence_",
    "isQuietSetup_",
    "assertAdminRunner_",
    "removeManagedSheetProtection_",
    "ensureManagedSheetProtection_",
    "applyStaffLockdown_",
    "adminShowAllTabs_",
    "setupStudentElectiveInputs_",
    "setupElectiveRulesTemplate_",
    "notifyStudentSetupComplete_",
    "adminSyncProgramsFromGitHub_",
    "adminInstallNightlyProgramsSync_",
    "adminRemoveNightlyProgramsSync_",
    "removeTriggersByHandler_",
    "adminRebuildCourseCatalog_",
    "markValidationForCell_",
    "normalizeCsvGrid_",
    "backupSheetSnapshot_",
    "writeSettingsStamp_"
  )
  "EligibilityEngine.gs" = @(
    "evaluateProgramsForStudent_",
    "makeProgramKey_",
    "slugProgramKeyPart_",
    "claimProgramKey_",
    "summarizeEvalForWebDetails_",
    "classifyEvalIssuesForWeb_",
    "buildProgramDetailsForWeb_",
    "readPinnedProgramKeysFromSheet_",
    "isTruthyPinValue_",
    "writeResultRowsToSheet_",
    "addPinColumnToRows_",
    "normalizeCompetitive_",
    "buildNotes_",
    "boolCmp_",
    "applyCompetitiveHighlight_",
    "isUncheckable_",
    "normalizeHttpUrlForOutput_",
    "normalizeConfidenceValue_",
    "isConfidenceUncheckable_",
    "deriveSnapshotResult_",
    "isAmbiguityText_",
    "firstAmbiguityReason_",
    "confidenceRank_",
    "capConfidence_",
    "confidenceFromScore_",
    "defaultUncheckableNextStep_",
    "evaluateConfidenceForProgram_",
    "buildConfidenceWarningPayload_",
    "formatAvgUsed_",
    "appendDatasetNotes_",
    "runConfidenceSelfTest_"
  )
  "EligibilityProgramsData.gs" = @(
    "indexHeader_",
    "normHeaderKey_",
    "requireProgramsColumns_",
    "readAvgRules_",
    "readElectiveRuleOverrides_",
    "resolveElectiveRuleOverrideText_",
    "combineRuleText_",
    "resolveAvgTotal_",
    "getStr_",
    "unifyEnglishReq_",
    "unifyEnglishMin_",
    "normalizeRequirementModeToken_",
    "inferRequirementMode_",
    "getSubjectRequirementMode_",
    "getSubjectRequirementText_",
    "toNumber_",
    "normalizeDateYmd_",
    "resolveDatasetDateFromPrograms_",
    "calculateDatasetAgeDays_",
    "canonKey_",
    "parseElectiveQty_",
    "parseAllowedGroups_",
    "parseElectiveRules_",
    "formatElectiveRuleSummary_",
    "parseCountToken_",
    "parseGroupsFromText_",
    "splitByAnd_",
    "parseScienceRequirementText_",
    "listExplorerProgramsForWeb_",
    "makeExplorerProgramKey_",
    "slugExplorerPart_"
  )
  "EligibilitySubjects.gs" = @(
    "buildCourseMap_",
    "courseAliases_",
    "evalSubject_",
    "evalScience_",
    "appendEval_",
    "buildScienceReq_",
    "parseAlternatives_",
    "normalizeRequirementToCourses_",
    "bestMarkWithEquivalencies_",
    "expandEquivalencies_",
    "extractCourseCodes_",
    "collectRequiredMarks_",
    "countRequiredSlots_"
  )
  "EligibilityElectives.gs" = @(
    "buildElectives_",
    "listElectiveCourseOptions_",
    "buildAutoElectivesFromCourseMap_",
    "mergeElectiveCandidates_",
    "normalizeCourseKey_",
    "formatCourseName_",
    "electiveGroupsForCourseKey_",
    "isLikelyLanguageCourse_",
    "isSeniorHighAdmissionLevel_",
    "isExcludedFromGroupDFallback_",
    "isLikelyGroupDAdmissionSubject_",
    "courseGroupMap_",
    "runElectiveRuleSelfTest_",
    "computeStudentAverage_",
    "selectBestElectives_",
    "pickBestElectiveSet_"
  )
  "EligibilityShared.gs" = @(
    "title_",
    "unique_"
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

  if ($fileName -ne "Code.gs") {
    $publicFns = @($actual | Where-Object { -not $_.EndsWith("_") })
    if ($publicFns.Count -gt 0) {
      Add-Issue("$fileName should not expose public top-level functions: $($publicFns -join ', ')")
    }
  }
}

$requiredHtml = @(
  "WebApp.html",
  "WebAppStyles.html",
  "WebAppBody.html",
  "WebAppScriptState.html",
  "WebAppScriptFunctions.html",
  "WebAppScriptInit.html"
)
foreach ($htmlFile in $requiredHtml) {
  $p = Join-Path $AppsScriptDir $htmlFile
  if (-not (Test-Path -LiteralPath $p -PathType Leaf)) {
    Add-Issue("Missing expected web app HTML fragment: $htmlFile")
  }
}

$webAppMainPath = Join-Path $AppsScriptDir "WebApp.html"
if (Test-Path -LiteralPath $webAppMainPath -PathType Leaf) {
  $webAppMain = Get-Content -LiteralPath $webAppMainPath -Raw
  $includeNames = @("WebAppStyles", "WebAppBody", "WebAppScriptState", "WebAppScriptFunctions", "WebAppScriptInit")
  foreach ($name in $includeNames) {
    $hasCommentInclude = $webAppMain -match [regex]::Escape("<!-- @include:$name -->")
    $hasTemplateInclude = $webAppMain -match ("includeHtml_\(\s*['""]" + [regex]::Escape($name) + "['""]\s*\)")
    if (-not ($hasCommentInclude -or $hasTemplateInclude)) {
      Add-Issue("WebApp.html missing include marker for $name")
    }
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
Write-Host (" - Checked module files: " + (($expectedByFile.Keys | Sort-Object) -join ", "))
Write-Host (" - Checked web app fragments: " + ($requiredHtml -join ", "))
exit 0
