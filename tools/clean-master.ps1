param(
  [string]$InputPath = ".\\ALBERTA_ADMISSIONS_MASTER_FINAL_v3.csv",
  [string]$OutputPath = ".\\data\\ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv",
  [string]$ProgramEvidencePath = ".\\PROGRAMS_ONLY.csv",
  [string]$FilterRulesPath = ".\\config\\nait_non_program_rules.json",
  [string]$NaitSeedPath = ".\\pipeline\\nait_program_seed.csv",
  [string]$MacewanSeedPath = ".\\pipeline\\macewan_program_seed.csv",
  [double]$MacewanMatchMinScore = 0.55,
  [double]$MacewanMatchMinGap = 0.08,
  [switch]$MacewanRequireFullSeedCoverage = $true,
  [string]$UalbertaMapPath = ".\\config\\ualberta_canonical_url_map.csv",
  [switch]$UalbertaRequireFullCoverage = $true,
  [string]$NorquestRulesPath = ".\\config\\norquest_non_program_rules.json",
  [string]$NorquestSeedPath = ".\\pipeline\\norquest_program_seed.csv",
  [string]$NaitLegacyAllowlistPath = ".\\config\\nait_legacy_allowlist.csv",
  [string]$ProgramOverridesPath = ".\\data\\PROGRAM_OVERRIDES.csv",
  [string]$StructuredExtractionPath = ".\\pipeline_artifacts\\extract\\programs_structured.csv",
  [string]$RulesetsPath = ".\\data\\RULESETS.csv",
  [switch]$DropNaitNonPrograms = $true,
  [switch]$DropNorQuestNonPrograms = $true,
  [switch]$DropMinors = $true,
  [switch]$DropExactDuplicates = $true
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Is-Blank([object]$v) {
  return ($null -eq $v) -or [string]::IsNullOrWhiteSpace([string]$v)
}

function Normalize-Text([object]$v) {
  if ($null -eq $v) { return "" }
  return ([string]$v -replace "\s+", " ").Trim()
}

function Normalize-ProgramKey([object]$v) {
  $t = (Normalize-Text $v).ToLowerInvariant()
  if (-not $t) { return "" }
  $t = $t.Replace("&amp;", " and ")
  $t = $t.Replace("&", " and ")
  $t = [regex]::Replace($t, "[^a-z0-9]+", " ")
  return ([string]$t -replace "\s+", " ").Trim()
}

function Normalize-UrlKey([object]$v) {
  $t = (Normalize-Text $v).ToLowerInvariant()
  if (-not $t) { return "" }
  $hashIndex = $t.IndexOf("#")
  if ($hashIndex -ge 0) {
    $t = $t.Substring(0, $hashIndex)
  }
  if ($t.EndsWith("/")) {
    $t = $t.Substring(0, $t.Length - 1)
  }
  return $t
}

function Is-HttpUrl([object]$value) {
  $t = Normalize-Text $value
  if (-not $t) { return $false }
  return ($t -match "^(?i:https?)://")
}

function Normalize-ProgramText([object]$v) {
  $s = Normalize-Text $v
  if (-not $s) { return "" }
  $t = $s.ToLowerInvariant()
  $t = [regex]::Replace($t, "\(.*?\)", " ")
  $t = [regex]::Replace($t, "[\u2010-\u2015]", " ")
  $t = [regex]::Replace($t, "[^a-z0-9 ]", " ")
  $t = [regex]::Replace($t, "\s+", " ").Trim()
  return $t
}

function Get-Tokens([object]$value) {
  $norm = Normalize-ProgramText $value
  if (-not $norm) { return @() }
  return @($norm.Split(" ") | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Sort-Object -Unique)
}

function Score-Jaccard([string[]]$a, [string[]]$b) {
  if (-not $a -or -not $b) { return 0.0 }
  $setA = @{}
  foreach ($x in @($a)) {
    if ([string]::IsNullOrWhiteSpace($x)) { continue }
    $setA[$x] = $true
  }
  $setB = @{}
  foreach ($x in @($b)) {
    if ([string]::IsNullOrWhiteSpace($x)) { continue }
    $setB[$x] = $true
  }
  if ($setA.Count -eq 0 -or $setB.Count -eq 0) { return 0.0 }

  $union = @{}
  foreach ($k in $setA.Keys) { $union[$k] = $true }
  foreach ($k in $setB.Keys) { $union[$k] = $true }

  $inter = 0
  foreach ($k in $setA.Keys) {
    if ($setB.ContainsKey($k)) { $inter++ }
  }
  if ($union.Count -eq 0) { return 0.0 }
  return [double]$inter / [double]$union.Count
}

function Copy-RowObject([object]$row) {
  $out = [ordered]@{}
  foreach ($prop in $row.PSObject.Properties) {
    $out[$prop.Name] = $prop.Value
  }
  return [pscustomobject]$out
}

function Infer-MacewanCredentialType([string]$programName) {
  $t = (Normalize-Text $programName).ToLowerInvariant()
  if (-not $t) { return "Other" }
  if ($t -match "diploma") { return "Diploma" }
  if ($t -match "certificate") { return "Certificate" }
  if ($t -match "degree|bachelor|major|honours") { return "Degree" }
  return "Other"
}

function Add-ToSet([hashtable]$set, [string]$key) {
  if ([string]::IsNullOrWhiteSpace($key)) { return }
  if (-not $set.ContainsKey($key)) {
    $set[$key] = $true
  }
}

function To-StringArray([object]$value) {
  $items = @()
  if ($null -eq $value) { return ,@() }
  if ($value -is [System.Collections.IEnumerable] -and -not ($value -is [string])) {
    foreach ($x in $value) {
      $s = Normalize-Text $x
      if ($s) { $items += $s }
    }
    return ,$items
  }
  $single = Normalize-Text $value
  if ($single) { $items += $single }
  return ,$items
}

function Get-PropValue([object]$row, [string[]]$names) {
  foreach ($n in $names) {
    $prop = $row.PSObject.Properties[$n]
    if ($prop) {
      return [string]$prop.Value
    }
  }
  return ""
}

function Get-RowProgramUrl([object]$row) {
  return Normalize-Text (Get-PropValue -row $row -names @("Program_URL", "Source_URL", "source_url", "program_url"))
}

function Normalize-NorquestCredentialType([string]$credential) {
  $c = (Normalize-Text $credential).ToLowerInvariant()
  if (-not $c) { return "Other" }
  if ($c -match "diploma") { return "Diploma" }
  if ($c -match "certificate") { return "Certificate" }
  if ($c -match "degree|bachelor") { return "Degree" }
  return "Other"
}

function Normalize-CredentialKey([object]$value) {
  return (Normalize-Text $value).ToLowerInvariant()
}

function Add-ToBucket([hashtable]$map, [string]$key, [object]$value) {
  if ([string]::IsNullOrWhiteSpace($key)) { return }
  if (-not $map.ContainsKey($key)) { $map[$key] = @() }
  $map[$key] = @($map[$key]) + $value
}

function Build-ProgramOverrideKey([string]$institution, [string]$program, [string]$credential) {
  $instKey = (Normalize-Text $institution).ToLowerInvariant()
  $programKey = Normalize-ProgramKey $program
  $credentialKey = Normalize-CredentialKey $credential
  if (-not $instKey -or -not $programKey) { return "" }
  return "{0}||{1}||{2}" -f $instKey, $programKey, $credentialKey
}

function Resolve-ProgramOverride(
  [hashtable]$overrides,
  [hashtable]$overridesByUrl,
  [hashtable]$overridesByInstitution,
  [string]$institution,
  [string]$program,
  [string]$credential,
  [string]$sourceUrl = ""
) {
  if ($null -eq $overrides -or $overrides.Count -eq 0) { return $null }
  $instKey = (Normalize-Text $institution).ToLowerInvariant()
  if (-not $instKey) { return $null }

  $sourceUrlKey = Normalize-UrlKey $sourceUrl
  if ($sourceUrlKey -and $null -ne $overridesByUrl -and $overridesByUrl.ContainsKey("$instKey||$sourceUrlKey")) {
    $urlCandidates = @($overridesByUrl["$instKey||$sourceUrlKey"])
    if ($urlCandidates.Count -eq 1) {
      return $urlCandidates[0]
    }

    $credKey = Normalize-CredentialKey $credential
    $credCandidates = @($urlCandidates | Where-Object { -not $_.Credential_Key -or $_.Credential_Key -eq $credKey })
    if ($credCandidates.Count -eq 1) {
      return $credCandidates[0]
    }

    $programKeyForUrl = Normalize-ProgramKey $program
    if ($programKeyForUrl) {
      $exactProgramCandidates = @($credCandidates | Where-Object { $_.Program_Key -eq $programKeyForUrl })
      if ($exactProgramCandidates.Count -eq 1) {
        return $exactProgramCandidates[0]
      }
    }
  }

  $exactKey = Build-ProgramOverrideKey -institution $institution -program $program -credential $credential
  if ($exactKey -and $overrides.ContainsKey($exactKey)) {
    return $overrides[$exactKey]
  }

  $fallbackKey = Build-ProgramOverrideKey -institution $institution -program $program -credential ""
  if ($fallbackKey -and $overrides.ContainsKey($fallbackKey)) {
    return $overrides[$fallbackKey]
  }

  if ($null -eq $overridesByInstitution -or -not $overridesByInstitution.ContainsKey($instKey)) {
    return $null
  }

  $programTokens = @(Get-Tokens $program)
  if ($programTokens.Count -eq 0) { return $null }

  $credKey = Normalize-CredentialKey $credential
  $candidates = @($overridesByInstitution[$instKey])
  if ($credKey) {
    $candidates = @($candidates | Where-Object { -not $_.Credential_Key -or $_.Credential_Key -eq $credKey })
  }
  if ($candidates.Count -eq 0) { return $null }

  $scored = @()
  foreach ($candidate in $candidates) {
    $candTokens = @($candidate.Program_Tokens)
    if ($candTokens.Count -eq 0) { continue }
    $score = Score-Jaccard -a $programTokens -b $candTokens
    if ($score -le 0) { continue }
    $scored += [pscustomobject]@{
      Score = [double]$score
      Override = $candidate
    }
  }
  if ($scored.Count -eq 0) { return $null }

  $scored = @($scored | Sort-Object @{ Expression = "Score"; Descending = $true })
  $best = $scored[0]
  if ($best.Score -lt 0.62) { return $null }
  if ($scored.Count -gt 1) {
    $gap = [double]$best.Score - [double]$scored[1].Score
    if ($gap -lt 0.10) { return $null }
  }
  return $best.Override
}

function New-ProgramOverrideRecord(
  [string]$institution,
  [string]$program,
  [string]$credentialType,
  [string]$includeOrExclude,
  [string]$requirementTypeOverride,
  [string]$minAvgOverride,
  [string]$electiveQtyOverride,
  [string]$avgTotalOverride,
  [string]$parentAdmissionsUrl,
  [string]$sourcePageUrl,
  [string]$needsParentSource,
  [string]$manualReviewFlag,
  [string]$notes
) {
  $programKey = Normalize-ProgramKey $program
  return [pscustomobject]@{
    Institution               = $institution
    Program                   = $program
    Program_Key               = $programKey
    Program_Tokens            = (Get-Tokens $program)
    Credential_Type           = $credentialType
    Credential_Key            = Normalize-CredentialKey $credentialType
    Include_Or_Exclude        = $includeOrExclude
    Requirement_Type_Override = $requirementTypeOverride
    Min_Avg_Override          = $minAvgOverride
    Elective_Qty_Override     = $electiveQtyOverride
    Avg_Total_Override        = $avgTotalOverride
    Parent_Admissions_Url     = $parentAdmissionsUrl
    Source_Page_Url           = $sourcePageUrl
    Needs_Parent_Source       = $needsParentSource
    Manual_Review_Flag        = $manualReviewFlag
    Notes                     = $notes
  }
}

function Add-ProgramOverrideUrlKeys([hashtable]$bucket, [object]$overrideRecord) {
  if ($null -eq $bucket -or $null -eq $overrideRecord) { return }
  $instKey = (Normalize-Text $overrideRecord.Institution).ToLowerInvariant()
  if (-not $instKey) { return }

  $urlCandidates = @()
  if (Is-HttpUrl $overrideRecord.Source_Page_Url) { $urlCandidates += (Normalize-UrlKey $overrideRecord.Source_Page_Url) }
  if (Is-HttpUrl $overrideRecord.Parent_Admissions_Url) { $urlCandidates += (Normalize-UrlKey $overrideRecord.Parent_Admissions_Url) }

  foreach ($urlKey in @($urlCandidates | Sort-Object -Unique)) {
    if (-not $urlKey) { continue }
    Add-ToBucket -map $bucket -key "$instKey||$urlKey" -value $overrideRecord
  }
}

function Get-StructuredConfidenceRank([object]$value) {
  $token = (Normalize-Text $value).ToLowerInvariant()
  switch ($token) {
    "high" { return 3 }
    "medium" { return 2 }
    "low" { return 1 }
    default { return 0 }
  }
}

function New-StructuredExtractionRecord(
  [string]$institution,
  [string]$program,
  [string]$credential,
  [string]$sourceUrl,
  [hashtable]$fieldPayloads
) {
  $programKey = Normalize-ProgramKey $program
  return [pscustomobject]@{
    Institution = $institution
    Program = $program
    Program_Key = $programKey
    Credential = $credential
    Credential_Key = Normalize-CredentialKey $credential
    Source_Url = $sourceUrl
    Source_Url_Key = Normalize-UrlKey $sourceUrl
    Field_Payloads = $fieldPayloads
  }
}

function Add-StructuredExtractionUrlKey([hashtable]$bucket, [object]$record) {
  if ($null -eq $bucket -or $null -eq $record) { return }
  $instKey = (Normalize-Text $record.Institution).ToLowerInvariant()
  $urlKey = Normalize-UrlKey $record.Source_Url
  if (-not $instKey -or -not $urlKey) { return }
  $bucket["$instKey||$urlKey"] = $record
}

function Resolve-StructuredExtraction(
  [hashtable]$recordsByKey,
  [hashtable]$recordsByUrl,
  [string]$institution,
  [string]$program,
  [string]$credential,
  [string]$sourceUrl = ""
) {
  $instKey = (Normalize-Text $institution).ToLowerInvariant()
  if (-not $instKey) { return $null }

  $sourceUrlKey = Normalize-UrlKey $sourceUrl
  if ($sourceUrlKey -and $recordsByUrl.ContainsKey("$instKey||$sourceUrlKey")) {
    return $recordsByUrl["$instKey||$sourceUrlKey"]
  }

  $exactKey = Build-ProgramOverrideKey -institution $institution -program $program -credential $credential
  if ($exactKey -and $recordsByKey.ContainsKey($exactKey)) {
    return $recordsByKey[$exactKey]
  }

  $fallbackKey = Build-ProgramOverrideKey -institution $institution -program $program -credential ""
  if ($fallbackKey -and $recordsByKey.ContainsKey($fallbackKey)) {
    return $recordsByKey[$fallbackKey]
  }

  return $null
}

function Should-ApplyStructuredField(
  [string]$canonicalField,
  [string]$candidateValue,
  [string]$candidateConfidence,
  [string]$existingValue
) {
  $candidate = Normalize-Text $candidateValue
  if (-not $candidate) { return $false }

  $rank = Get-StructuredConfidenceRank $candidateConfidence
  if ($rank -ge 2) { return $true }
  if ($rank -lt 1) { return $false }

  $existing = (Normalize-Text $existingValue).ToLowerInvariant()
  if ($canonicalField -in @("Requirement_Type", "HS_Diploma_Req", "Math_Assessment_Flag", "ELP_Tests_Mentioned")) {
    return (-not $existing) -or ($existing -in @("unknown", "none", "null", "nan"))
  }

  return $false
}

function Normalize-RequirementTypeValue([string]$value, [object]$row) {
  $text = Normalize-Text $value
  $text = ($text -replace "(?i);\s*notes:\s*notes:\s*", "; notes: ").Trim()
  $lower = $text.ToLowerInvariant()

  $hasSubjectSignal = @(
    (Get-PropValue -row $row -names @("English_Req")),
    (Get-PropValue -row $row -names @("Math_Req")),
    (Get-PropValue -row $row -names @("Social_Req")),
    (Get-PropValue -row $row -names @("Science_Req")),
    (Get-PropValue -row $row -names @("Min_Avg_Final")),
    (Get-PropValue -row $row -names @("Elective_Qty"))
  ) | Where-Object { -not (Is-Blank $_) }
  $hasSubjectSignal = @($hasSubjectSignal)
  $hasCourseMinimumSignal = @(
    (Get-PropValue -row $row -names @("English_Min")),
    (Get-PropValue -row $row -names @("Math_Min")),
    (Get-PropValue -row $row -names @("Social_Min")),
    (Get-PropValue -row $row -names @("Science_Min"))
  ) | Where-Object { -not (Is-Blank $_) }
  $hasCourseMinimumSignal = @($hasCourseMinimumSignal)
  $hasOverallAverageSignal = (-not (Is-Blank (Get-PropValue -row $row -names @("Min_Avg_Final")))) -or (-not (Is-Blank (Get-PropValue -row $row -names @("Avg_Total"))))

  $mathAssessment = (Normalize-Text $row.Math_Assessment_Flag).ToLowerInvariant()

  if (-not $text -or $lower -eq "unknown") {
    if ($mathAssessment -eq "yes") { return "placement_assessment" }
    if ($hasSubjectSignal.Count -gt 0) {
      if ((-not $hasOverallAverageSignal) -and $hasCourseMinimumSignal.Count -gt 0) {
        return "course_min_only"
      }
      return "alberta_high_school_courses"
    }
    return $text
  }

  if ($mathAssessment -eq "yes" -and -not $lower.StartsWith("placement_assessment")) {
    $notesIndex = $lower.IndexOf("; notes:")
    if ($notesIndex -ge 0) {
      return "placement_assessment$($text.Substring($notesIndex))"
    }
    return "placement_assessment"
  }

  if ($lower -match "^(alberta_high_school_courses|course_min_only|placement_assessment|post_secondary_pathway|regular_admission|first_year_admission)(;|$)") {
    return $text
  }

  if ($lower -match "placement|assessment|accuplacer|casper") {
    return "placement_assessment; notes: $text"
  }

  if ($lower -match "regular admission") {
    return "regular_admission; notes: $text"
  }

  if ($hasSubjectSignal.Count -gt 0 -or $lower -match "see degree|refer to degree|group [abcd]|english 30|mathematics 30|biology 30|chemistry 30|physics 30|science 30|social studies 30") {
    return "alberta_high_school_courses; notes: $text"
  }

  return $text
}

function Convert-CountTokenToInt([object]$value) {
  $text = (Normalize-Text $value).ToLowerInvariant()
  if (-not $text) { return 0 }

  if ($text -match "\b(\d+)\b") {
    try { return [int][double]$Matches[1] } catch { return 0 }
  }

  switch ($text) {
    "one" { return 1 }
    "two" { return 2 }
    "three" { return 3 }
    "four" { return 4 }
    "five" { return 5 }
    "six" { return 6 }
    "seven" { return 7 }
    "eight" { return 8 }
    "nine" { return 9 }
    "ten" { return 10 }
    default { return 0 }
  }
}

function Get-RequirementUnitCount([object]$value) {
  $text = Normalize-Text $value
  if (-not $text) { return 0 }

  if ($text -match "\b(one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+of\b") {
    return (Convert-CountTokenToInt $Matches[1])
  }

  if ($text -match "\bor\b") {
    return 1
  }

  $parts = @(
    [regex]::Split($text, "\s*,\s*|\s+and\s+") |
      ForEach-Object { Normalize-Text $_ } |
      Where-Object { -not (Is-Blank $_) }
  )
  $courseParts = @(
    $parts |
      Where-Object { $_ -match "\b(english|ela|math|mathematics|social|aboriginal|biology|chemistry|physics|science|physical education|recreation)\b" } |
      Sort-Object -Unique
  )
  if ($courseParts.Count -gt 1 -and $courseParts.Count -le 6) {
    return $courseParts.Count
  }

  return 1
}

function Get-InferredAvgTotal([object]$row) {
  $reqType = (Normalize-Text $row.Requirement_Type).ToLowerInvariant()
  if ($reqType.Contains("placement_assessment")) {
    return ""
  }

  $count = 0
  if (-not (Is-Blank $row.English_Req)) { $count++ }
  if (-not (Is-Blank $row.Math_Req)) { $count++ }
  if (-not (Is-Blank $row.Social_Req)) { $count++ }
  if (-not (Is-Blank $row.Science_Req)) { $count += (Get-RequirementUnitCount $row.Science_Req) }

  $electiveRaw = Normalize-Text $row.Elective_Qty
  if ($electiveRaw) {
    $electiveValue = Convert-CountTokenToInt $electiveRaw
    if ($electiveValue -gt 0) {
      $count += $electiveValue
    }
  }

  $hasAdmissionSignal = (-not (Is-Blank $row.Min_Avg_Final)) -or $reqType.StartsWith("alberta_high_school_courses")
  if ($hasAdmissionSignal -and $count -eq 5) {
    return [string]$count
  }
  return ""
}

function Is-ActiveOverrideStatus([object]$status) {
  $raw = (Normalize-Text $status).ToLowerInvariant()
  if (-not $raw) { return $true }
  if ($raw -in @("inactive", "disabled", "archived", "off", "no", "false", "0")) { return $false }
  return $true
}

function Parse-TruthyFlag([object]$value, [bool]$defaultValue = $false) {
  $raw = (Normalize-Text $value).ToLowerInvariant()
  if (-not $raw) { return $defaultValue }
  if ($raw -in @("yes", "y", "true", "1", "required")) { return $true }
  if ($raw -in @("no", "n", "false", "0", "not_required")) { return $false }
  return $defaultValue
}

function Parse-CredentialScopeTokens([object]$value) {
  $scope = Normalize-Text $value
  if (-not $scope -or $scope.ToLowerInvariant() -eq "any") { return ,@() }
  $tokens = @(
    $scope -split "[|,;/]" |
      ForEach-Object { (Normalize-Text $_).ToLowerInvariant() } |
      Where-Object { $_ }
  )
  return ,$tokens
}

function Credential-MatchesScope([string]$credentialType, [string[]]$scopeTokens) {
  if ($null -eq $scopeTokens -or $scopeTokens.Count -eq 0) { return $true }
  $cred = (Normalize-Text $credentialType).ToLowerInvariant()
  if (-not $cred) { return $false }
  foreach ($token in $scopeTokens) {
    if (-not $token) { continue }
    if ($cred -like "*$token*") { return $true }
  }
  return $false
}

function Ensure-Dir([string]$path) {
  $dir = Split-Path -Parent $path
  if (-not (Test-Path $dir)) {
    New-Item -ItemType Directory -Path $dir | Out-Null
  }
}

if (-not (Test-Path $InputPath)) {
  throw "Input file not found: $InputPath"
}

$rows = Import-Csv $InputPath

if ($DropMinors) {
  # Minors are not standalone admissions targets for high-school applicants (typically chosen within a degree).
  $rows = $rows | Where-Object { $_.Credential_Type -ne "Minor" }
}

$naitSeedNames = @{}
$naitSeedRowsByKey = @{}
$naitAllowlistNames = @{}
$naitAllowlistUrls = @{}
$naitLegacyAllowlistNames = @{}
$naitBlockedUrlPatterns = @()
$naitBlockedNamePatterns = @()
$naitEvidenceTokens = @("not a program page")
$naitEvidenceByName = @{}
$naitStats = @{
  nait_rows_examined = 0
  dropped_evidence_non_program = 0
  dropped_blocked_url = 0
  dropped_blocked_name = 0
  dropped_not_in_seed = 0
  kept_allowlist_override = 0
  kept_legacy_allowlist = 0
  kept_seed_match = 0
  seed_backfill_added = 0
  seed_url_filled = 0
}

$norquestSeedNames = @{}
$norquestSeedRowsByKey = @{}
$norquestAllowlistNames = @{}
$norquestAllowlistUrls = @{}
$norquestBlockedUrlPatterns = @()
$norquestBlockedNamePatterns = @()
$norquestEvidenceTokens = @("not a program page")
$norquestEvidenceByName = @{}
$norquestStats = @{
  norquest_rows_examined = 0
  dropped_evidence_non_program = 0
  dropped_blocked_url = 0
  dropped_blocked_name = 0
  dropped_not_in_seed = 0
  kept_allowlist_override = 0
  kept_seed_match = 0
  seed_backfill_added = 0
  seed_url_filled = 0
}

$macewanSeedRows = @()
$macewanStats = @{
  seed_rows_loaded = 0
  matched_seed_rows = 0
  unresolved_seed_rows = 0
  ambiguous_seed_rows = 0
  rows_written = 0
  rows_with_program_url = 0
}

$ualbertaUrlMap = @{}
$ualbertaMapDuplicates = @()
$ualbertaStats = @{
  map_rows_loaded = 0
  rows_examined = 0
  rows_mapped = 0
  rows_missing_map = 0
  rows_invalid_map_url = 0
  rows_with_program_url = 0
}

$programOverridesByKey = @{}
$programOverridesByUrlKey = @{}
$programOverridesByInstitution = @{}
$programOverrideStats = @{
  rows_loaded = 0
  include_rows = 0
  exclude_rows = 0
  disabled_rows = 0
  duplicate_keys_overwritten = 0
  row_include_forced = 0
  row_excluded = 0
  field_overrides_applied = 0
  url_overrides_applied = 0
}

$structuredByKey = @{}
$structuredByUrlKey = @{}
$structuredStats = @{
  rows_loaded = 0
  rows_applied = 0
  field_values_applied = 0
}

$rulesetsByInstitution = @{}
$rulesetStats = @{
  rows_loaded = 0
  rows_skipped = 0
  rows_with_default_avg_total = 0
  rows_with_placement_required = 0
  rows_applied = 0
  avg_total_filled = 0
  placement_flags_set = 0
}

if (Test-Path $FilterRulesPath) {
  $rulesJson = Get-Content -Raw $FilterRulesPath | ConvertFrom-Json
  $naitBlockedUrlPatterns = To-StringArray $rulesJson.blocked_url_patterns
  $naitBlockedNamePatterns = To-StringArray $rulesJson.blocked_name_patterns
  $tokenValues = To-StringArray $rulesJson.evidence_not_program_tokens
  if ($tokenValues.Count -gt 0) {
    $naitEvidenceTokens = @($tokenValues | ForEach-Object { $_.ToLowerInvariant() })
  }
  foreach ($name in (To-StringArray $rulesJson.allowlist_program_names)) {
    Add-ToSet -set $naitAllowlistNames -key (Normalize-ProgramKey $name)
  }
  foreach ($url in (To-StringArray $rulesJson.allowlist_urls)) {
    Add-ToSet -set $naitAllowlistUrls -key (Normalize-UrlKey $url)
  }
}

if (Test-Path $NorquestRulesPath) {
  $rulesJson = Get-Content -Raw $NorquestRulesPath | ConvertFrom-Json
  $norquestBlockedUrlPatterns = To-StringArray $rulesJson.blocked_url_patterns
  $norquestBlockedNamePatterns = To-StringArray $rulesJson.blocked_name_patterns
  $tokenValues = To-StringArray $rulesJson.evidence_not_program_tokens
  if ($tokenValues.Count -gt 0) {
    $norquestEvidenceTokens = @($tokenValues | ForEach-Object { $_.ToLowerInvariant() })
  }
  foreach ($name in (To-StringArray $rulesJson.allowlist_program_names)) {
    Add-ToSet -set $norquestAllowlistNames -key (Normalize-ProgramKey $name)
  }
  foreach ($url in (To-StringArray $rulesJson.allowlist_urls)) {
    Add-ToSet -set $norquestAllowlistUrls -key (Normalize-UrlKey $url)
  }
}

if (Test-Path $NaitSeedPath) {
  foreach ($seed in (Import-Csv $NaitSeedPath)) {
    $name = Normalize-Text (Get-PropValue -row $seed -names @("program_name", "Program"))
    $key = Normalize-ProgramKey $name
    $url = Normalize-Text (Get-PropValue -row $seed -names @("program_url", "Program_URL", "source_url", "url"))
    Add-ToSet -set $naitSeedNames -key $key
    if ($key -and -not $naitSeedRowsByKey.ContainsKey($key)) {
      $naitSeedRowsByKey[$key] = [pscustomobject]@{
        Program = $name
        Program_URL = $url
      }
    }
  }
}

if (Test-Path $NorquestSeedPath) {
  foreach ($seed in (Import-Csv $NorquestSeedPath)) {
    $name = Normalize-Text (Get-PropValue -row $seed -names @("program_name", "Program"))
    $key = Normalize-ProgramKey $name
    $url = Normalize-Text (Get-PropValue -row $seed -names @("program_url", "Program_URL", "source_url", "url"))
    $credential = Normalize-NorquestCredentialType (Get-PropValue -row $seed -names @("credential", "Credential", "credential_type", "Credential_Type"))
    Add-ToSet -set $norquestSeedNames -key $key
    if ($key -and -not $norquestSeedRowsByKey.ContainsKey($key)) {
      $norquestSeedRowsByKey[$key] = [pscustomobject]@{
        Program = $name
        Credential_Type = $credential
        Program_URL = $url
      }
    }
  }
}

if (Test-Path $MacewanSeedPath) {
  foreach ($seed in (Import-Csv $MacewanSeedPath)) {
    $name = Normalize-Text (Get-PropValue -row $seed -names @("program_name", "Program"))
    $seedUrl = Normalize-Text (Get-PropValue -row $seed -names @("program_url_seed", "program_url", "Program_URL", "url"))
    $requirementsUrl = Normalize-Text (Get-PropValue -row $seed -names @("requirements_url", "requirement_url"))
    $preferredUrl = ""
    if (Is-HttpUrl $requirementsUrl) {
      $preferredUrl = $requirementsUrl
    } elseif (Is-HttpUrl $seedUrl) {
      $preferredUrl = $seedUrl
    }
    if (-not $name -or -not $preferredUrl) { continue }
    $macewanSeedRows += [pscustomobject]@{
      Program          = $name
      Program_Key      = (Normalize-ProgramKey $name)
      Program_Url_Seed = $seedUrl
      Requirements_Url = $requirementsUrl
      Preferred_Url    = $preferredUrl
      Tokens           = (Get-Tokens $name)
    }
  }
}
$macewanStats.seed_rows_loaded = @($macewanSeedRows).Count

if (Test-Path $UalbertaMapPath) {
  foreach ($mapRow in (Import-Csv $UalbertaMapPath)) {
    $name = Normalize-Text (Get-PropValue -row $mapRow -names @("program_name", "Program"))
    $nameKey = Normalize-ProgramKey $name
    $url = Normalize-Text (Get-PropValue -row $mapRow -names @("program_url", "Program_URL", "source_url", "url"))
    if (-not $nameKey) { continue }

    if ($ualbertaUrlMap.ContainsKey($nameKey)) {
      $ualbertaMapDuplicates += $name
      continue
    }

    $ualbertaUrlMap[$nameKey] = [pscustomobject]@{
      Program = $name
      Program_URL = $url
    }
  }
}
$ualbertaStats.map_rows_loaded = $ualbertaUrlMap.Count

if (Test-Path $NaitLegacyAllowlistPath) {
  foreach ($allow in (Import-Csv $NaitLegacyAllowlistPath)) {
    $name = Normalize-ProgramKey (Get-PropValue -row $allow -names @("program_name", "Program"))
    Add-ToSet -set $naitLegacyAllowlistNames -key $name
  }
}

if (Test-Path $ProgramEvidencePath) {
  foreach ($e in (Import-Csv $ProgramEvidencePath)) {
    $inst = Normalize-Text (Get-PropValue -row $e -names @("institution", "Institution"))
    $instKey = $inst.ToUpperInvariant()
    if ($instKey -ne "NAIT" -and $instKey -ne "NORQUEST") { continue }
    $name = Normalize-ProgramKey (Get-PropValue -row $e -names @("program_name", "Program"))
    if (-not $name) { continue }
    $notes = Normalize-Text (Get-PropValue -row $e -names @("notes_uncertain", "Notes_Uncertain", "notes", "Notes"))
    if (-not $notes) { continue }
    if ($instKey -eq "NAIT") {
      if ($naitEvidenceByName.ContainsKey($name)) {
        $naitEvidenceByName[$name] = "{0} | {1}" -f $naitEvidenceByName[$name], $notes
      } else {
        $naitEvidenceByName[$name] = $notes
      }
    } else {
      if ($norquestEvidenceByName.ContainsKey($name)) {
        $norquestEvidenceByName[$name] = "{0} | {1}" -f $norquestEvidenceByName[$name], $notes
      } else {
        $norquestEvidenceByName[$name] = $notes
      }
    }
  }
}

if (Test-Path $ProgramOverridesPath) {
  foreach ($overrideRow in (Import-Csv $ProgramOverridesPath)) {
    $institution = Normalize-Text (Get-PropValue -row $overrideRow -names @("institution", "Institution"))
    $program = Normalize-Text (Get-PropValue -row $overrideRow -names @("program", "Program"))
    if (-not $institution -or -not $program) { continue }

    $status = Normalize-Text (Get-PropValue -row $overrideRow -names @("status", "Status"))
    if (-not (Is-ActiveOverrideStatus $status)) {
      $programOverrideStats.disabled_rows++
      continue
    }

    $credentialType = Normalize-Text (Get-PropValue -row $overrideRow -names @("credential_type", "Credential_Type"))
    $includeOrExcludeRaw = (Normalize-Text (Get-PropValue -row $overrideRow -names @("include_or_exclude", "Include_Or_Exclude"))).ToLowerInvariant()
    $includeOrExclude = ""
    if ($includeOrExcludeRaw -eq "include" -or $includeOrExcludeRaw -eq "exclude") {
      $includeOrExclude = $includeOrExcludeRaw
    }

    $key = Build-ProgramOverrideKey -institution $institution -program $program -credential $credentialType
    if (-not $key) { continue }

    if ($programOverridesByKey.ContainsKey($key)) {
      $programOverrideStats.duplicate_keys_overwritten++
    }

    $overrideRecord = New-ProgramOverrideRecord `
      -institution $institution `
      -program $program `
      -credentialType $credentialType `
      -includeOrExclude $includeOrExclude `
      -requirementTypeOverride (Normalize-Text (Get-PropValue -row $overrideRow -names @("requirement_type_override", "Requirement_Type_Override"))) `
      -minAvgOverride (Normalize-Text (Get-PropValue -row $overrideRow -names @("min_avg_override", "Min_Avg_Override"))) `
      -electiveQtyOverride (Normalize-Text (Get-PropValue -row $overrideRow -names @("elective_qty_override", "Elective_Qty_Override"))) `
      -avgTotalOverride (Normalize-Text (Get-PropValue -row $overrideRow -names @("avg_total_override", "Avg_Total_Override"))) `
      -parentAdmissionsUrl (Normalize-Text (Get-PropValue -row $overrideRow -names @("parent_admissions_url", "Parent_Admissions_Url"))) `
      -sourcePageUrl (Normalize-Text (Get-PropValue -row $overrideRow -names @("source_page_url", "Source_Page_Url"))) `
      -needsParentSource (Normalize-Text (Get-PropValue -row $overrideRow -names @("needs_parent_source", "Needs_Parent_Source"))) `
      -manualReviewFlag (Normalize-Text (Get-PropValue -row $overrideRow -names @("manual_review_flag", "Manual_Review_Flag"))) `
      -notes (Normalize-Text (Get-PropValue -row $overrideRow -names @("notes", "Notes")))

    $programOverridesByKey[$key] = $overrideRecord
    Add-ProgramOverrideUrlKeys -bucket $programOverridesByUrlKey -overrideRecord $overrideRecord
    Add-ToBucket -map $programOverridesByInstitution -key ((Normalize-Text $institution).ToLowerInvariant()) -value $overrideRecord

    $programOverrideStats.rows_loaded++
    if ($includeOrExclude -eq "include") { $programOverrideStats.include_rows++ }
    if ($includeOrExclude -eq "exclude") { $programOverrideStats.exclude_rows++ }
  }
}

$structuredFieldMap = [ordered]@{
  min_avg_final = "Min_Avg_Final"
  competitive_final = "Competitive_Final"
  avg_total = "Avg_Total"
  english_req = "English_Req"
  english_min = "English_Min"
  math_req = "Math_Req"
  math_min = "Math_Min"
  social_req = "Social_Req"
  social_min = "Social_Min"
  science_req = "Science_Req"
  science_min = "Science_Min"
  bio_30_req = "Bio_30_Req"
  chem_30_req = "Chem_30_Req"
  phys_30_req = "Phys_30_Req"
  sci_30_req = "Sci_30_Req"
  elective_qty = "Elective_Qty"
  elective_pool = "Elective_Pool"
  requirement_type = "Requirement_Type"
  hs_diploma_req = "HS_Diploma_Req"
  math_assessment_flag = "Math_Assessment_Flag"
  elp_tests_mentioned = "ELP_Tests_Mentioned"
}

if (Test-Path $StructuredExtractionPath) {
  foreach ($structuredRow in (Import-Csv $StructuredExtractionPath)) {
    $institution = Normalize-Text (Get-PropValue -row $structuredRow -names @("institution", "Institution"))
    $program = Normalize-Text (Get-PropValue -row $structuredRow -names @("program_name", "Program"))
    if (-not $institution -or -not $program) { continue }

    $credential = Normalize-Text (Get-PropValue -row $structuredRow -names @("credential", "Credential", "Credential_Type"))
    $sourceUrl = Normalize-Text (Get-PropValue -row $structuredRow -names @("source_url", "Source_Url", "Program_URL"))
    $fieldPayloads = @{}
    foreach ($fieldKey in $structuredFieldMap.Keys) {
      $fieldValue = Normalize-Text (Get-PropValue -row $structuredRow -names @($fieldKey))
      $fieldConfidence = Normalize-Text (Get-PropValue -row $structuredRow -names @("${fieldKey}_confidence"))
      $fieldPayloads[$fieldKey] = [pscustomobject]@{
        Value = $fieldValue
        Confidence = $fieldConfidence
      }
    }

    $record = New-StructuredExtractionRecord `
      -institution $institution `
      -program $program `
      -credential $credential `
      -sourceUrl $sourceUrl `
      -fieldPayloads $fieldPayloads

    $key = Build-ProgramOverrideKey -institution $institution -program $program -credential $credential
    if ($key) {
      $structuredByKey[$key] = $record
    }
    Add-StructuredExtractionUrlKey -bucket $structuredByUrlKey -record $record
    $structuredStats.rows_loaded++
  }
}

if (Test-Path $RulesetsPath) {
  foreach ($rulesetRow in (Import-Csv $RulesetsPath)) {
    $institution = Normalize-Text (Get-PropValue -row $rulesetRow -names @("institution", "Institution"))
    if (-not $institution) {
      $rulesetStats.rows_skipped++
      continue
    }

    $defaultAvgTotalRaw = Normalize-Text (Get-PropValue -row $rulesetRow -names @("default_avg_total", "Default_Avg_Total"))
    $defaultAvgTotal = 0
    if ($defaultAvgTotalRaw) {
      try { $defaultAvgTotal = [int][double]$defaultAvgTotalRaw } catch { $defaultAvgTotal = 0 }
    }

    $placementRequired = Parse-TruthyFlag (Get-PropValue -row $rulesetRow -names @("placement_required", "Placement_Required")) $false
    $credentialScope = Normalize-Text (Get-PropValue -row $rulesetRow -names @("credential_scope", "Credential_Scope"))
    $credentialTokens = Parse-CredentialScopeTokens $credentialScope
    $requirementTypePattern = (Normalize-Text (Get-PropValue -row $rulesetRow -names @("requirement_type_pattern", "Requirement_Type_Pattern"))).ToLowerInvariant()
    $rulesetKey = Normalize-Text (Get-PropValue -row $rulesetRow -names @("ruleset_key", "Ruleset_Key"))

    if ($defaultAvgTotal -le 0 -and -not $placementRequired) {
      $rulesetStats.rows_skipped++
      continue
    }

    $specificity = 0
    if ($credentialTokens.Count -gt 0) { $specificity += 1 }
    if ($requirementTypePattern) { $specificity += 1 }

    $ruleRecord = [pscustomobject]@{
      Institution_Key = $institution.ToLowerInvariant()
      Ruleset_Key = $rulesetKey
      Credential_Tokens = $credentialTokens
      Requirement_Type_Pattern = $requirementTypePattern
      Default_Avg_Total = $defaultAvgTotal
      Placement_Required = $placementRequired
      Specificity = $specificity
    }

    Add-ToBucket -map $rulesetsByInstitution -key $ruleRecord.Institution_Key -value $ruleRecord
    $rulesetStats.rows_loaded++
    if ($defaultAvgTotal -gt 0) { $rulesetStats.rows_with_default_avg_total++ }
    if ($placementRequired) { $rulesetStats.rows_with_placement_required++ }
  }

  foreach ($instKey in @($rulesetsByInstitution.Keys)) {
    $rulesetsByInstitution[$instKey] = @(
      $rulesetsByInstitution[$instKey] |
        Sort-Object @{ Expression = "Specificity"; Descending = $true }, @{ Expression = "Ruleset_Key"; Descending = $false }
    )
  }
}

if ($programOverridesByKey.Count -gt 0) {
  $rows = @(
    $rows | Where-Object {
      $inst = Normalize-Text $_.Institution
      $programName = Normalize-Text $_.Program
      $credentialType = Normalize-Text $_.Credential_Type
      $programUrl = Get-RowProgramUrl $_
      $override = Resolve-ProgramOverride `
        -overrides $programOverridesByKey `
        -overridesByUrl $programOverridesByUrlKey `
        -overridesByInstitution $programOverridesByInstitution `
        -institution $inst `
        -program $programName `
        -credential $credentialType `
        -sourceUrl $programUrl
      if ($null -eq $override) { return $true }
      if ($override.Include_Or_Exclude -eq "exclude") {
        $programOverrideStats.row_excluded++
        return $false
      }
      return $true
    }
  )
}

if ($DropNaitNonPrograms -or $DropNorQuestNonPrograms) {
  $rows = $rows | Where-Object {
    $inst = Normalize-Text $_.Institution
    $programName = Normalize-Text $_.Program
    $credentialType = Normalize-Text $_.Credential_Type
    $programKey = Normalize-ProgramKey $programName
    $programUrl = Get-RowProgramUrl $_
    $programUrlKey = Normalize-UrlKey $programUrl
    $programOverride = Resolve-ProgramOverride `
      -overrides $programOverridesByKey `
      -overridesByUrl $programOverridesByUrlKey `
      -overridesByInstitution $programOverridesByInstitution `
      -institution $inst `
      -program $programName `
      -credential $credentialType `
      -sourceUrl $programUrl

    if ($inst -eq "NAIT" -and $DropNaitNonPrograms) {
      if ($null -ne $programOverride -and $programOverride.Include_Or_Exclude -eq "include") {
        $programOverrideStats.row_include_forced++
        return $true
      }
      $naitStats.nait_rows_examined++

      $evidenceNotes = ""
      if ($programKey -and $naitEvidenceByName.ContainsKey($programKey)) {
        $evidenceNotes = [string]$naitEvidenceByName[$programKey]
      }
      $evidenceLow = $evidenceNotes.ToLowerInvariant()
      foreach ($token in $naitEvidenceTokens) {
        if ($token -and $evidenceLow.Contains($token)) {
          $naitStats.dropped_evidence_non_program++
          return $false
        }
      }

      foreach ($pattern in $naitBlockedUrlPatterns) {
        if (-not $pattern) { continue }
        if ($programUrl -and $programUrl -match $pattern) {
          $naitStats.dropped_blocked_url++
          return $false
        }
      }

      foreach ($pattern in $naitBlockedNamePatterns) {
        if (-not $pattern) { continue }
        if ($programName -match $pattern) {
          $naitStats.dropped_blocked_name++
          return $false
        }
      }

      if (($programKey -and $naitAllowlistNames.ContainsKey($programKey)) -or
        ($programUrlKey -and $naitAllowlistUrls.ContainsKey($programUrlKey))) {
        $naitStats.kept_allowlist_override++
        return $true
      }

      if ($naitSeedNames.Count -eq 0 -and $programKey -and $naitLegacyAllowlistNames.ContainsKey($programKey)) {
        $naitStats.kept_legacy_allowlist++
        return $true
      }

      if ($programKey -and $naitSeedNames.ContainsKey($programKey)) {
        $naitStats.kept_seed_match++
        return $true
      }

      $naitStats.dropped_not_in_seed++
      return $false
    }

    if ($inst -eq "NorQuest" -and $DropNorQuestNonPrograms) {
      if ($null -ne $programOverride -and $programOverride.Include_Or_Exclude -eq "include") {
        $programOverrideStats.row_include_forced++
        return $true
      }
      $norquestStats.norquest_rows_examined++

      $evidenceNotes = ""
      if ($programKey -and $norquestEvidenceByName.ContainsKey($programKey)) {
        $evidenceNotes = [string]$norquestEvidenceByName[$programKey]
      }
      $evidenceLow = $evidenceNotes.ToLowerInvariant()
      foreach ($token in $norquestEvidenceTokens) {
        if ($token -and $evidenceLow.Contains($token)) {
          $norquestStats.dropped_evidence_non_program++
          return $false
        }
      }

      foreach ($pattern in $norquestBlockedUrlPatterns) {
        if (-not $pattern) { continue }
        if ($programUrl -and $programUrl -match $pattern) {
          $norquestStats.dropped_blocked_url++
          return $false
        }
      }

      foreach ($pattern in $norquestBlockedNamePatterns) {
        if (-not $pattern) { continue }
        if ($programName -match $pattern) {
          $norquestStats.dropped_blocked_name++
          return $false
        }
      }

      if (($programKey -and $norquestAllowlistNames.ContainsKey($programKey)) -or
        ($programUrlKey -and $norquestAllowlistUrls.ContainsKey($programUrlKey))) {
        $norquestStats.kept_allowlist_override++
        return $true
      }

      if ($programKey -and $norquestSeedNames.ContainsKey($programKey)) {
        $norquestStats.kept_seed_match++
        return $true
      }

      $norquestStats.dropped_not_in_seed++
      return $false
    }

    if ($inst -eq "NAIT" -or $inst -eq "NorQuest") {
      return $true
    }
    return $true
  }
}

$canonical = foreach ($r in $rows) {
  $programUrl = Get-RowProgramUrl $r

  $englishReq = if (-not (Is-Blank $r.English_Req)) { $r.English_Req } else { $r.Eng_Req }
  $englishMin = if (-not (Is-Blank $r.English_Min)) { $r.English_Min } else { $r.Eng_Min }

  [pscustomobject]@{
    Institution          = $r.Institution
    Program              = $r.Program
    Credential_Type      = $r.Credential_Type
    Status               = $r.Status
    Program_URL          = $programUrl

    Min_Avg_Final        = $r.Min_Avg_Final
    Competitive_Final    = $r.Competitive_Final
    Avg_Total            = (Normalize-Text (Get-PropValue -row $r -names @("Avg_Total", "avg_total")))

    English_Req          = $englishReq
    English_Min          = $englishMin
    Eng_30_2_Allowed     = $r.Eng_30_2_Allowed

    Math_Req             = $r.Math_Req
    Math_Min             = $r.Math_Min

    Social_Req           = $r.Social_Req
    Social_Min           = $r.Social_Min

    Science_Req          = $r.Science_Req
    Science_Min          = $r.Science_Min
    Bio_30_Req           = $r.Bio_30_Req
    Chem_30_Req          = $r.Chem_30_Req
    Phys_30_Req          = $r.Phys_30_Req
    Sci_30_Req           = $r.Sci_30_Req

    Elective_Qty         = $r.Elective_Qty
    Elective_Pool        = $r.Elective_Pool
    Pool_Allows_Group_A  = $r.Pool_Allows_Group_A
    Pool_Allows_Group_B  = $r.Pool_Allows_Group_B
    Pool_Allows_Group_C  = $r.Pool_Allows_Group_C
    Pool_Allows_Group_D  = $r.Pool_Allows_Group_D

    Requirement_Type     = $r.Requirement_Type
    HS_Diploma_Req       = $r.HS_Diploma_Req
    Math_Assessment_Flag = $r.Math_Assessment_Flag
    ELP_Tests_Mentioned  = $r.ELP_Tests_Mentioned
  }
}

if ($DropNaitNonPrograms -and $naitSeedRowsByKey.Count -gt 0) {
  $existingNaitKeys = @{}
  foreach ($row in @($canonical | Where-Object { $_.Institution -eq "NAIT" })) {
    $key = Normalize-ProgramKey $row.Program
    if ($key) { $existingNaitKeys[$key] = $true }
  }

  $backfillRows = @()
  foreach ($key in $naitSeedRowsByKey.Keys) {
    if ($existingNaitKeys.ContainsKey($key)) { continue }
    $seedRow = $naitSeedRowsByKey[$key]
    $seedProgram = Normalize-Text $seedRow.Program
    if (-not $seedProgram) { continue }

    $seedOverride = Resolve-ProgramOverride `
      -overrides $programOverridesByKey `
      -overridesByUrl $programOverridesByUrlKey `
      -overridesByInstitution $programOverridesByInstitution `
      -institution "NAIT" `
      -program $seedProgram `
      -credential "" `
      -sourceUrl (Normalize-Text $seedRow.Program_URL)
    if ($null -ne $seedOverride -and $seedOverride.Include_Or_Exclude -eq "exclude") {
      $programOverrideStats.row_excluded++
      continue
    }

    $backfillRows += [pscustomobject]@{
      Institution          = "NAIT"
      Program              = $seedProgram
      Credential_Type      = Infer-MacewanCredentialType $seedProgram
      Status               = "Active"
      Program_URL          = (Normalize-Text $seedRow.Program_URL)

      Min_Avg_Final        = ""
      Competitive_Final    = ""
      Avg_Total            = ""

      English_Req          = ""
      English_Min          = ""
      Eng_30_2_Allowed     = ""

      Math_Req             = ""
      Math_Min             = ""

      Social_Req           = ""
      Social_Min           = ""

      Science_Req          = ""
      Science_Min          = ""
      Bio_30_Req           = ""
      Chem_30_Req          = ""
      Phys_30_Req          = ""
      Sci_30_Req           = ""

      Elective_Qty         = ""
      Elective_Pool        = ""
      Pool_Allows_Group_A  = ""
      Pool_Allows_Group_B  = ""
      Pool_Allows_Group_C  = ""
      Pool_Allows_Group_D  = ""

      Requirement_Type     = "Unknown"
      HS_Diploma_Req       = "Unknown"
      Math_Assessment_Flag = "Unknown"
      ELP_Tests_Mentioned  = ""
    }
  }

  if ($backfillRows.Count -gt 0) {
    $naitStats.seed_backfill_added = $backfillRows.Count
    $canonical = @($canonical) + @($backfillRows)
  }
}

if ($DropNorQuestNonPrograms -and $norquestSeedRowsByKey.Count -gt 0) {
  $existingNorquestKeys = @{}
  foreach ($row in @($canonical | Where-Object { $_.Institution -eq "NorQuest" })) {
    $key = Normalize-ProgramKey $row.Program
    if ($key) { $existingNorquestKeys[$key] = $true }
  }

  $backfillRows = @()
  foreach ($key in $norquestSeedRowsByKey.Keys) {
    if ($existingNorquestKeys.ContainsKey($key)) { continue }
    $seedRow = $norquestSeedRowsByKey[$key]
    $seedProgram = Normalize-Text $seedRow.Program
    $seedUrl = Normalize-Text $seedRow.Program_URL
    $seedOverride = Resolve-ProgramOverride `
      -overrides $programOverridesByKey `
      -overridesByUrl $programOverridesByUrlKey `
      -overridesByInstitution $programOverridesByInstitution `
      -institution "NorQuest" `
      -program $seedProgram `
      -credential (Normalize-Text $seedRow.Credential_Type) `
      -sourceUrl $seedUrl
    if ($null -ne $seedOverride -and $seedOverride.Include_Or_Exclude -eq "exclude") {
      $programOverrideStats.row_excluded++
      continue
    }

    $backfillRows += [pscustomobject]@{
      Institution          = "NorQuest"
      Program              = $seedProgram
      Credential_Type      = (Normalize-NorquestCredentialType $seedRow.Credential_Type)
      Status               = "Active"
      Program_URL          = $seedUrl

      Min_Avg_Final        = ""
      Competitive_Final    = ""
      Avg_Total            = ""

      English_Req          = ""
      English_Min          = ""
      Eng_30_2_Allowed     = ""

      Math_Req             = ""
      Math_Min             = ""

      Social_Req           = ""
      Social_Min           = ""

      Science_Req          = ""
      Science_Min          = ""
      Bio_30_Req           = ""
      Chem_30_Req          = ""
      Phys_30_Req          = ""
      Sci_30_Req           = ""

      Elective_Qty         = ""
      Elective_Pool        = ""
      Pool_Allows_Group_A  = ""
      Pool_Allows_Group_B  = ""
      Pool_Allows_Group_C  = ""
      Pool_Allows_Group_D  = ""

      Requirement_Type     = "Unknown"
      HS_Diploma_Req       = "Unknown"
      Math_Assessment_Flag = "Unknown"
      ELP_Tests_Mentioned  = ""
    }
  }

  if ($backfillRows.Count -gt 0) {
    $norquestStats.seed_backfill_added = $backfillRows.Count
    $canonical = @($canonical) + @($backfillRows)
  }
}

if ($naitSeedRowsByKey.Count -gt 0 -or $norquestSeedRowsByKey.Count -gt 0) {
  foreach ($row in @($canonical)) {
    $inst = Normalize-Text $row.Institution
    if ($inst -ne "NAIT" -and $inst -ne "NorQuest") { continue }

    $programKey = Normalize-ProgramKey $row.Program
    if (-not $programKey) { continue }

    $currentUrl = Normalize-Text $row.Program_URL
    if (Is-HttpUrl $currentUrl) { continue }

    if ($inst -eq "NAIT" -and $naitSeedRowsByKey.ContainsKey($programKey)) {
      $seedUrl = Normalize-Text $naitSeedRowsByKey[$programKey].Program_URL
      if (Is-HttpUrl $seedUrl) {
        $row.Program_URL = $seedUrl
        $naitStats.seed_url_filled++
        continue
      }
    }

    if ($inst -eq "NorQuest" -and $norquestSeedRowsByKey.ContainsKey($programKey)) {
      $seedUrl = Normalize-Text $norquestSeedRowsByKey[$programKey].Program_URL
      if (Is-HttpUrl $seedUrl) {
        $row.Program_URL = $seedUrl
        $norquestStats.seed_url_filled++
      }
    }
  }
}

if ($macewanSeedRows.Count -gt 0 -or $MacewanRequireFullSeedCoverage) {
  if ($MacewanRequireFullSeedCoverage -and $macewanSeedRows.Count -eq 0) {
    throw "MacEwan seed file is required but no rows were loaded: $MacewanSeedPath"
  }

  $templateRow = $null
  if (@($canonical).Count -gt 0) {
    $templateRow = @($canonical)[0]
  }
  if ($null -eq $templateRow) {
    throw "Could not build MacEwan canonical rows: canonical template row missing"
  }

  $existingMacewanRows = @($canonical | Where-Object { $_.Institution -eq "MacEwan" })
  $nonMacewanRows = @($canonical | Where-Object { $_.Institution -ne "MacEwan" })

  $candidateRows = @()
  foreach ($row in $existingMacewanRows) {
    $candidateRows += [pscustomobject]@{
      Row         = $row
      ProgramNorm = (Normalize-ProgramText $row.Program)
      Tokens      = (Get-Tokens $row.Program)
    }
  }

  $rebuiltMacewanRows = @()
  $macewanSeedExcludedByOverride = 0
  foreach ($seed in $macewanSeedRows) {
    $seedName = Normalize-Text $seed.Program
    $seedTokens = @($seed.Tokens)
    $scored = @()

    foreach ($candidate in $candidateRows) {
      $score = Score-Jaccard -a $seedTokens -b @($candidate.Tokens)
      if ($score -le 0) { continue }
      $scored += [pscustomobject]@{
        Score       = [double]$score
        ProgramNorm = $candidate.ProgramNorm
        Row         = $candidate.Row
      }
    }

    $isMatch = $false
    $isAmbiguous = $false
    $bestRow = $null
    $bestScore = 0.0

    if ($scored.Count -gt 0) {
      $scored = @($scored | Sort-Object @{ Expression = "Score"; Descending = $true })
      $bestScore = [double]$scored[0].Score
      if ($bestScore -ge $MacewanMatchMinScore) {
        $near = @($scored | Where-Object { ($bestScore - [double]$_.Score) -lt $MacewanMatchMinGap })
        $nearNorms = @($near | Select-Object -ExpandProperty ProgramNorm -Unique)
        if ($nearNorms.Count -le 1) {
          $isMatch = $true
          $bestRow = $scored[0].Row
        } else {
          $isAmbiguous = $true
        }
      }
    }

    $seedRequirementsUrl = Normalize-Text $seed.Requirements_Url
    $seedProgramUrl = Normalize-Text $seed.Program_Url_Seed
    $seedPreferredUrl = Normalize-Text $seed.Preferred_Url
    $fallbackUrl = ""
    if (Is-HttpUrl $seedRequirementsUrl) {
      $fallbackUrl = $seedRequirementsUrl
    } elseif (Is-HttpUrl $seedProgramUrl) {
      $fallbackUrl = $seedProgramUrl
    } elseif (Is-HttpUrl $seedPreferredUrl) {
      $fallbackUrl = $seedPreferredUrl
    }

    $seedOverride = Resolve-ProgramOverride `
      -overrides $programOverridesByKey `
      -overridesByUrl $programOverridesByUrlKey `
      -overridesByInstitution $programOverridesByInstitution `
      -institution "MacEwan" `
      -program $seedName `
      -credential (Infer-MacewanCredentialType $seedName) `
      -sourceUrl $fallbackUrl
    if ($null -ne $seedOverride -and $seedOverride.Include_Or_Exclude -eq "exclude") {
      $macewanSeedExcludedByOverride++
      $programOverrideStats.row_excluded++
      continue
    }

    if ($isMatch -and $bestRow) {
      $rebuilt = Copy-RowObject $bestRow
      $rebuilt.Institution = "MacEwan"
      $rebuilt.Program = $seedName
      if (Is-Blank $rebuilt.Status) {
        $rebuilt.Status = "Active"
      }
      if (Is-Blank $rebuilt.Credential_Type) {
        $rebuilt.Credential_Type = Infer-MacewanCredentialType $seedName
      }

      $matchedUrl = Normalize-Text $bestRow.Program_URL
      if ((Is-HttpUrl $matchedUrl) -and ($matchedUrl -match "calendar\.macewan\.ca")) {
        $rebuilt.Program_URL = $matchedUrl
      } elseif ($fallbackUrl) {
        $rebuilt.Program_URL = $fallbackUrl
      } elseif (Is-HttpUrl $matchedUrl) {
        $rebuilt.Program_URL = $matchedUrl
      } else {
        $rebuilt.Program_URL = ""
      }

      $macewanStats.matched_seed_rows++
      $rebuiltMacewanRows += $rebuilt
      continue
    }

    $blank = [ordered]@{}
    foreach ($prop in $templateRow.PSObject.Properties) {
      $blank[$prop.Name] = ""
    }
    $rebuilt = [pscustomobject]$blank
    $rebuilt.Institution = "MacEwan"
    $rebuilt.Program = $seedName
    $rebuilt.Credential_Type = Infer-MacewanCredentialType $seedName
    $rebuilt.Status = "Active"
    $rebuilt.Program_URL = $fallbackUrl
    $rebuilt.Requirement_Type = "See Degree"
    $rebuilt.HS_Diploma_Req = "Unknown"
    $rebuilt.Math_Assessment_Flag = "Unknown"

    if ($isAmbiguous) {
      $macewanStats.ambiguous_seed_rows++
    }
    $macewanStats.unresolved_seed_rows++
    $rebuiltMacewanRows += $rebuilt
  }

  $expectedMacewanRows = $macewanSeedRows.Count - $macewanSeedExcludedByOverride
  if ($MacewanRequireFullSeedCoverage -and ($rebuiltMacewanRows.Count -ne $expectedMacewanRows)) {
    throw (
      "MacEwan seed coverage mismatch: expected {0} rows, rebuilt {1}" -f
      $expectedMacewanRows, $rebuiltMacewanRows.Count
    )
  }

  $macewanStats.rows_written = @($rebuiltMacewanRows).Count
  $macewanStats.rows_with_program_url = @($rebuiltMacewanRows | Where-Object { Is-HttpUrl $_.Program_URL }).Count
  $canonical = @($nonMacewanRows) + @($rebuiltMacewanRows)
}

$ualbertaMissingPrograms = @()
$ualbertaInvalidMapPrograms = @()
$ualbertaSeenMapKeys = @{}
foreach ($row in @($canonical | Where-Object { $_.Institution -eq "UAlberta" })) {
  $ualbertaStats.rows_examined++
  $programName = Normalize-Text $row.Program
  $programKey = Normalize-ProgramKey $programName
  if (-not $programKey -or -not $ualbertaUrlMap.ContainsKey($programKey)) {
    $ualbertaStats.rows_missing_map++
    $ualbertaMissingPrograms += $programName
    continue
  }

  Add-ToSet -set $ualbertaSeenMapKeys -key $programKey

  $mapUrl = Normalize-Text $ualbertaUrlMap[$programKey].Program_URL
  if (-not (Is-HttpUrl $mapUrl)) {
    $ualbertaStats.rows_invalid_map_url++
    $ualbertaInvalidMapPrograms += $programName
    continue
  }

  $row.Program_URL = $mapUrl
  $ualbertaStats.rows_mapped++
}

$ualbertaStats.rows_with_program_url = @(
  $canonical |
    Where-Object { $_.Institution -eq "UAlberta" -and (Is-HttpUrl $_.Program_URL) }
).Count

if ($UalbertaRequireFullCoverage) {
  if (-not (Test-Path $UalbertaMapPath)) {
    throw "UAlberta map file not found: $UalbertaMapPath"
  }
  if ($ualbertaUrlMap.Count -eq 0) {
    throw "UAlberta map has no rows: $UalbertaMapPath"
  }
  if ($ualbertaMapDuplicates.Count -gt 0) {
    $examples = @($ualbertaMapDuplicates | Select-Object -First 25) -join "; "
    throw "UAlberta map has duplicate program_name keys ($($ualbertaMapDuplicates.Count)). Examples: $examples"
  }
  if ($ualbertaMissingPrograms.Count -gt 0) {
    $examples = @($ualbertaMissingPrograms | Select-Object -First 25) -join "; "
    throw "UAlberta canonical rows missing from URL map ($($ualbertaMissingPrograms.Count)). Examples: $examples"
  }
  if ($ualbertaInvalidMapPrograms.Count -gt 0) {
    $examples = @($ualbertaInvalidMapPrograms | Select-Object -First 25) -join "; "
    throw "UAlberta URL map rows missing/non-http program_url ($($ualbertaInvalidMapPrograms.Count)). Examples: $examples"
  }

  $unusedMapPrograms = @()
  foreach ($key in $ualbertaUrlMap.Keys) {
    if ($ualbertaSeenMapKeys.ContainsKey($key)) { continue }
    $unusedMapPrograms += (Normalize-Text $ualbertaUrlMap[$key].Program)
  }
  if ($unusedMapPrograms.Count -gt 0) {
    $examples = @($unusedMapPrograms | Select-Object -First 25) -join "; "
    throw "UAlberta URL map rows were not matched to canonical rows ($($unusedMapPrograms.Count)). Examples: $examples"
  }
}

if ($structuredByKey.Count -gt 0 -or $structuredByUrlKey.Count -gt 0) {
  foreach ($row in @($canonical)) {
    $structured = Resolve-StructuredExtraction `
      -recordsByKey $structuredByKey `
      -recordsByUrl $structuredByUrlKey `
      -institution (Normalize-Text $row.Institution) `
      -program (Normalize-Text $row.Program) `
      -credential (Normalize-Text $row.Credential_Type) `
      -sourceUrl (Normalize-Text $row.Program_URL)
    if ($null -eq $structured) { continue }

    $rowTouched = $false
    foreach ($fieldKey in $structuredFieldMap.Keys) {
      if (-not $structured.Field_Payloads.ContainsKey($fieldKey)) { continue }
      $payload = $structured.Field_Payloads[$fieldKey]
      $candidateValue = Normalize-Text $payload.Value
      $candidateConfidence = Normalize-Text $payload.Confidence
      $canonicalField = [string]$structuredFieldMap[$fieldKey]
      $existingValue = Normalize-Text $row.$canonicalField

      if (-not (Should-ApplyStructuredField `
        -canonicalField $canonicalField `
        -candidateValue $candidateValue `
        -candidateConfidence $candidateConfidence `
        -existingValue $existingValue)) {
        continue
      }

      $row.$canonicalField = $candidateValue
      $structuredStats.field_values_applied++
      $rowTouched = $true
    }

    if ($rowTouched) {
      $structuredStats.rows_applied++
    }
  }
}

foreach ($row in @($canonical)) {
  if (-not (Is-Blank $row.Requirement_Type)) {
    $row.Requirement_Type = Normalize-RequirementTypeValue -value $row.Requirement_Type -row $row
  }

  if (Is-Blank $row.Avg_Total) {
    $inferredAvgTotal = Get-InferredAvgTotal $row
    if ($inferredAvgTotal) {
      $row.Avg_Total = $inferredAvgTotal
    }
  }
}

if ($rulesetsByInstitution.Count -gt 0) {
  foreach ($row in @($canonical)) {
    $instKey = (Normalize-Text $row.Institution).ToLowerInvariant()
    if (-not $instKey -or -not $rulesetsByInstitution.ContainsKey($instKey)) { continue }

    $rulesForInst = @($rulesetsByInstitution[$instKey])
    if ($rulesForInst.Count -eq 0) { continue }

    $rowCredential = Normalize-Text $row.Credential_Type
    $rowReqType = (Normalize-Text $row.Requirement_Type).ToLowerInvariant()
    $hasRuleSignal = $false
    foreach ($fieldName in @("Min_Avg_Final", "English_Req", "Math_Req", "Social_Req", "Science_Req", "Elective_Qty", "HS_Diploma_Req")) {
      $fieldValue = (Normalize-Text $row.$fieldName).ToLowerInvariant()
      if ($fieldValue -and $fieldValue -notin @("unknown", "none", "null", "nan", "no")) {
        $hasRuleSignal = $true
        break
      }
    }
    $matchedRule = $null
    foreach ($rule in $rulesForInst) {
      if (-not (Credential-MatchesScope -credentialType $rowCredential -scopeTokens @($rule.Credential_Tokens))) {
        continue
      }
      if ($rule.Requirement_Type_Pattern -and $rowReqType) {
        if (-not $rowReqType.Contains($rule.Requirement_Type_Pattern)) {
          continue
        }
      } elseif ($rule.Requirement_Type_Pattern -and -not $hasRuleSignal) {
        continue
      }
      $matchedRule = $rule
      break
    }
    if ($null -eq $matchedRule) { continue }

    $rowApplied = $false
    $currentAvgTotal = Normalize-Text $row.Avg_Total
    if ($matchedRule.Default_Avg_Total -gt 0 -and -not $currentAvgTotal) {
      $row.Avg_Total = [string]$matchedRule.Default_Avg_Total
      $rulesetStats.avg_total_filled++
      $rowApplied = $true
    }

    if (($rowReqType -in @("", "unknown")) -and $matchedRule.Requirement_Type_Pattern -and $hasRuleSignal) {
      $row.Requirement_Type = Normalize-RequirementTypeValue -value $matchedRule.Requirement_Type_Pattern -row $row
      $rowApplied = $true
    }

    if ($matchedRule.Placement_Required) {
      $flagRaw = (Normalize-Text $row.Math_Assessment_Flag).ToLowerInvariant()
      if (-not $flagRaw -or $flagRaw -in @("unknown", "nan", "none", "null")) {
        $row.Math_Assessment_Flag = "Yes"
        $rulesetStats.placement_flags_set++
        $rowApplied = $true
      }
    }

    if ($rowApplied) {
      $rulesetStats.rows_applied++
    }
  }
}

if ($programOverridesByKey.Count -gt 0) {
  foreach ($row in @($canonical)) {
    $rowProgramUrl = Normalize-Text $row.Program_URL
    $override = Resolve-ProgramOverride `
      -overrides $programOverridesByKey `
      -overridesByUrl $programOverridesByUrlKey `
      -overridesByInstitution $programOverridesByInstitution `
      -institution (Normalize-Text $row.Institution) `
      -program (Normalize-Text $row.Program) `
      -credential (Normalize-Text $row.Credential_Type) `
      -sourceUrl $rowProgramUrl
    if ($null -eq $override) { continue }

    $rowTouched = $false
    if ($override.Requirement_Type_Override) {
      $row.Requirement_Type = $override.Requirement_Type_Override
      $rowTouched = $true
    }
    if ($override.Min_Avg_Override) {
      $row.Min_Avg_Final = $override.Min_Avg_Override
      $rowTouched = $true
    }
    if ($override.Elective_Qty_Override) {
      $row.Elective_Qty = $override.Elective_Qty_Override
      $rowTouched = $true
    }
    if ($override.Avg_Total_Override) {
      $row.Avg_Total = $override.Avg_Total_Override
      $rowTouched = $true
    }

    $overrideUrl = ""
    if (Is-HttpUrl $override.Parent_Admissions_Url) {
      $overrideUrl = $override.Parent_Admissions_Url
    } elseif (Is-HttpUrl $override.Source_Page_Url) {
      $overrideUrl = $override.Source_Page_Url
    }

    $existingUrl = Normalize-Text $row.Program_URL
    if ($overrideUrl -and -not (Is-HttpUrl $existingUrl)) {
      $row.Program_URL = $overrideUrl
      $programOverrideStats.url_overrides_applied++
      $rowTouched = $true
    }

    if ($rowTouched) {
      $programOverrideStats.field_overrides_applied++
    }
  }
}

if ($norquestSeedRowsByKey.Count -gt 0) {
  foreach ($row in @($canonical | Where-Object { $_.Institution -eq "NorQuest" })) {
    $programKey = Normalize-ProgramKey $row.Program
    if (-not $programKey -or -not $norquestSeedRowsByKey.ContainsKey($programKey)) { continue }
    $seedRow = $norquestSeedRowsByKey[$programKey]

    if (Is-Blank $row.Credential_Type) {
      $row.Credential_Type = (Normalize-NorquestCredentialType $seedRow.Credential_Type)
    }
    if (Is-Blank $row.Status) {
      $row.Status = "Active"
    }
  }
}

foreach ($row in @($canonical)) {
  $normalizedRequirementType = Normalize-RequirementTypeValue -value (Normalize-Text $row.Requirement_Type) -row $row
  $normalizedRequirementType = (Normalize-Text $normalizedRequirementType).Replace("notes: notes:", "notes: ")
  if ($normalizedRequirementType) {
    $row.Requirement_Type = $normalizedRequirementType
  }

  $reqTypeLower = (Normalize-Text $row.Requirement_Type).ToLowerInvariant()
  $notesIndex = $reqTypeLower.IndexOf("; notes:")
  $notesSuffix = ""
  if ($notesIndex -ge 0) {
    $notesSuffix = (Normalize-Text $row.Requirement_Type).Substring($notesIndex)
  }

  if ($reqTypeLower.StartsWith("placement_assessment")) {
    $row.Avg_Total = ""
  }

  $hasSubjectRequirements = @(
    $row.English_Req,
    $row.Math_Req,
    $row.Social_Req,
    $row.Science_Req
  ) | Where-Object { -not (Is-Blank $_) }
  $hasSubjectRequirements = @($hasSubjectRequirements)
  $hasCourseMinimums = @(
    $row.English_Min,
    $row.Math_Min,
    $row.Social_Min,
    $row.Science_Min
  ) | Where-Object { -not (Is-Blank $_) }
  $hasCourseMinimums = @($hasCourseMinimums)

  if (
    $reqTypeLower.StartsWith("alberta_high_school_courses") `
    -and (Is-Blank $row.Min_Avg_Final) `
    -and (Is-Blank $row.Avg_Total) `
    -and $hasSubjectRequirements.Count -gt 0 `
    -and $hasCourseMinimums.Count -gt 0
  ) {
    $row.Requirement_Type = "course_min_only$notesSuffix"
    $reqTypeLower = (Normalize-Text $row.Requirement_Type).ToLowerInvariant()
  }

  if ($reqTypeLower.StartsWith("regular_admission") -and $reqTypeLower.Contains("post-secondary pathway")) {
    $row.Requirement_Type = "post_secondary_pathway$notesSuffix"
    $row.HS_Diploma_Req = "No"
    $row.Math_Assessment_Flag = "No"
  }
}

if ($DropExactDuplicates) {
  if ($macewanSeedRows.Count -gt 0) {
    $nonMacewanDedup = @(
      $canonical |
        Where-Object { $_.Institution -ne "MacEwan" } |
        Sort-Object * -Unique
    )
    $macewanRowsPreserved = @(
      $canonical |
        Where-Object { $_.Institution -eq "MacEwan" }
    )
    $canonical = @($nonMacewanDedup) + @($macewanRowsPreserved)
  } else {
    $canonical = $canonical | Sort-Object * -Unique
  }
}

Ensure-Dir $OutputPath
$csvLines = $canonical | ConvertTo-Csv -NoTypeInformation
# Write UTF-8 without BOM so tools parse headers correctly across environments.
# Write to a temp file first so we can replace atomically (and avoid partial writes).
$tmpPath = "$OutputPath.tmp"
[System.IO.File]::WriteAllLines($tmpPath, $csvLines, [System.Text.UTF8Encoding]::new($false))
$finalPath = $OutputPath
try {
  Move-Item -Force -LiteralPath $tmpPath -Destination $OutputPath
} catch {
  $fallback = "$OutputPath.new"
  Move-Item -Force -LiteralPath $tmpPath -Destination $fallback
  $finalPath = $fallback
  Write-Warning "Could not overwrite $OutputPath (file in use). Wrote: $fallback"
}

Write-Host "Wrote $($canonical.Count) rows -> $finalPath"
if ($DropNaitNonPrograms) {
  Write-Host "NAIT cleanup summary:"
  Write-Host ("  nait_rows_examined: {0}" -f $naitStats.nait_rows_examined)
  Write-Host ("  seed_names_loaded: {0}" -f $naitSeedNames.Count)
  Write-Host ("  legacy_allowlist_names_loaded: {0}" -f $naitLegacyAllowlistNames.Count)
  Write-Host ("  evidence_names_loaded: {0}" -f $naitEvidenceByName.Count)
  Write-Host ("  dropped_evidence_non_program: {0}" -f $naitStats.dropped_evidence_non_program)
  Write-Host ("  dropped_blocked_url: {0}" -f $naitStats.dropped_blocked_url)
  Write-Host ("  dropped_blocked_name: {0}" -f $naitStats.dropped_blocked_name)
  Write-Host ("  dropped_not_in_seed: {0}" -f $naitStats.dropped_not_in_seed)
  Write-Host ("  kept_allowlist_override: {0}" -f $naitStats.kept_allowlist_override)
  Write-Host ("  kept_legacy_allowlist: {0}" -f $naitStats.kept_legacy_allowlist)
  Write-Host ("  kept_seed_match: {0}" -f $naitStats.kept_seed_match)
  Write-Host ("  seed_backfill_added: {0}" -f $naitStats.seed_backfill_added)
  Write-Host ("  seed_url_filled: {0}" -f $naitStats.seed_url_filled)
}
if ($DropNorQuestNonPrograms) {
  Write-Host "NorQuest cleanup summary:"
  Write-Host ("  norquest_rows_examined: {0}" -f $norquestStats.norquest_rows_examined)
  Write-Host ("  seed_names_loaded: {0}" -f $norquestSeedNames.Count)
  Write-Host ("  evidence_names_loaded: {0}" -f $norquestEvidenceByName.Count)
  Write-Host ("  dropped_evidence_non_program: {0}" -f $norquestStats.dropped_evidence_non_program)
  Write-Host ("  dropped_blocked_url: {0}" -f $norquestStats.dropped_blocked_url)
  Write-Host ("  dropped_blocked_name: {0}" -f $norquestStats.dropped_blocked_name)
  Write-Host ("  dropped_not_in_seed: {0}" -f $norquestStats.dropped_not_in_seed)
  Write-Host ("  kept_allowlist_override: {0}" -f $norquestStats.kept_allowlist_override)
  Write-Host ("  kept_seed_match: {0}" -f $norquestStats.kept_seed_match)
  Write-Host ("  seed_backfill_added: {0}" -f $norquestStats.seed_backfill_added)
  Write-Host ("  seed_url_filled: {0}" -f $norquestStats.seed_url_filled)
}
if ($macewanStats.seed_rows_loaded -gt 0 -or $MacewanRequireFullSeedCoverage) {
  Write-Host "MacEwan seed summary:"
  Write-Host ("  seed_rows_loaded: {0}" -f $macewanStats.seed_rows_loaded)
  Write-Host ("  matched_seed_rows: {0}" -f $macewanStats.matched_seed_rows)
  Write-Host ("  unresolved_seed_rows: {0}" -f $macewanStats.unresolved_seed_rows)
  Write-Host ("  ambiguous_seed_rows: {0}" -f $macewanStats.ambiguous_seed_rows)
  Write-Host ("  rows_written: {0}" -f $macewanStats.rows_written)
  Write-Host ("  rows_with_program_url: {0}" -f $macewanStats.rows_with_program_url)
}
if ($ualbertaStats.map_rows_loaded -gt 0 -or $UalbertaRequireFullCoverage) {
  Write-Host "UAlberta URL map summary:"
  Write-Host ("  map_rows_loaded: {0}" -f $ualbertaStats.map_rows_loaded)
  Write-Host ("  rows_examined: {0}" -f $ualbertaStats.rows_examined)
  Write-Host ("  rows_mapped: {0}" -f $ualbertaStats.rows_mapped)
  Write-Host ("  rows_missing_map: {0}" -f $ualbertaStats.rows_missing_map)
  Write-Host ("  rows_invalid_map_url: {0}" -f $ualbertaStats.rows_invalid_map_url)
  Write-Host ("  rows_with_program_url: {0}" -f $ualbertaStats.rows_with_program_url)
}
if ((Test-Path $RulesetsPath) -or $rulesetStats.rows_loaded -gt 0) {
  Write-Host "Rulesets summary:"
  Write-Host ("  ruleset_rows_loaded: {0}" -f $rulesetStats.rows_loaded)
  Write-Host ("  ruleset_rows_skipped: {0}" -f $rulesetStats.rows_skipped)
  Write-Host ("  rows_with_default_avg_total: {0}" -f $rulesetStats.rows_with_default_avg_total)
  Write-Host ("  rows_with_placement_required: {0}" -f $rulesetStats.rows_with_placement_required)
  Write-Host ("  canonical_rows_touched: {0}" -f $rulesetStats.rows_applied)
  Write-Host ("  avg_total_filled: {0}" -f $rulesetStats.avg_total_filled)
  Write-Host ("  placement_flags_set: {0}" -f $rulesetStats.placement_flags_set)
}
if ((Test-Path $StructuredExtractionPath) -or $structuredStats.rows_loaded -gt 0) {
  Write-Host "Structured extraction summary:"
  Write-Host ("  structured_rows_loaded: {0}" -f $structuredStats.rows_loaded)
  Write-Host ("  canonical_rows_touched: {0}" -f $structuredStats.rows_applied)
  Write-Host ("  field_values_applied: {0}" -f $structuredStats.field_values_applied)
}
if ((Test-Path $ProgramOverridesPath) -or $programOverrideStats.rows_loaded -gt 0) {
  Write-Host "Program overrides summary:"
  Write-Host ("  override_rows_loaded: {0}" -f $programOverrideStats.rows_loaded)
  Write-Host ("  include_rows: {0}" -f $programOverrideStats.include_rows)
  Write-Host ("  exclude_rows: {0}" -f $programOverrideStats.exclude_rows)
  Write-Host ("  disabled_rows_skipped: {0}" -f $programOverrideStats.disabled_rows)
  Write-Host ("  duplicate_keys_overwritten: {0}" -f $programOverrideStats.duplicate_keys_overwritten)
  Write-Host ("  rows_excluded: {0}" -f $programOverrideStats.row_excluded)
  Write-Host ("  rows_force_kept: {0}" -f $programOverrideStats.row_include_forced)
  Write-Host ("  rows_with_field_overrides: {0}" -f $programOverrideStats.field_overrides_applied)
  Write-Host ("  rows_with_url_overrides: {0}" -f $programOverrideStats.url_overrides_applied)
}
