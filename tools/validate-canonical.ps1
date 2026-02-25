param(
  [string]$CsvPath = ".\\data\\ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv",
  [string]$BaselinePath = ".\\out\\last_good_programs.csv",
  [string]$NaitSeedPath = ".\\pipeline\\nait_program_seed.csv",
  [string]$NaitLegacyAllowlistPath = ".\\config\\nait_legacy_allowlist.csv",
  [string]$NaitRulesPath = ".\\config\\nait_non_program_rules.json",
  [string]$MacewanSeedPath = ".\\pipeline\\macewan_program_seed.csv",
  [string]$UalbertaMapPath = ".\\config\\ualberta_canonical_url_map.csv",
  [string]$NorquestSeedPath = ".\\pipeline\\norquest_program_seed.csv",
  [string]$NorquestRulesPath = ".\\config\\norquest_non_program_rules.json",
  [string]$ProgramEvidencePath = ".\\PROGRAMS_ONLY.csv",
  [string]$ProgramOverridesPath = ".\\data\\PROGRAM_OVERRIDES.csv",
  [switch]$RequireUalbertaMap = $true,
  [int]$MinRows = 100,
  [double]$MaxRowDropPercent = 35,
  [string[]]$RequiredInstitutions = @("NAIT", "NorQuest", "MacEwan", "UAlberta")
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-HeaderNames([object[]]$rows) {
  if (-not $rows -or $rows.Count -eq 0) { return @() }
  return @($rows[0].PSObject.Properties.Name)
}

function Has-Column([string[]]$headers, [string]$name) {
  return $headers -contains $name
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

function Is-ActiveOverrideStatus([object]$value) {
  $raw = (Normalize-Text $value).ToLowerInvariant()
  if (-not $raw) { return $true }
  if ($raw -in @("inactive", "disabled", "archived", "off", "no", "false", "0")) { return $false }
  return $true
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

function Add-ToSet([hashtable]$set, [string]$key) {
  if ([string]::IsNullOrWhiteSpace($key)) { return }
  if (-not $set.ContainsKey($key)) {
    $set[$key] = $true
  }
}

function Add-ToNestedSet([hashtable]$map, [string]$instKey, [string]$valueKey) {
  if ([string]::IsNullOrWhiteSpace($instKey) -or [string]::IsNullOrWhiteSpace($valueKey)) { return }
  if (-not $map.ContainsKey($instKey)) {
    $map[$instKey] = @{}
  }
  Add-ToSet -set $map[$instKey] -key $valueKey
}

function In-NestedSet([hashtable]$map, [string]$instKey, [string]$valueKey) {
  if ([string]::IsNullOrWhiteSpace($instKey) -or [string]::IsNullOrWhiteSpace($valueKey)) { return $false }
  if (-not $map.ContainsKey($instKey)) { return $false }
  return $map[$instKey].ContainsKey($valueKey)
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

function Resolve-CanonicalPath([string]$path) {
  $primary = $path
  if ($primary.ToLowerInvariant().EndsWith(".new")) {
    return $primary
  }
  $fallback = "$primary.new"
  $primaryExists = Test-Path $primary
  $fallbackExists = Test-Path $fallback
  if ($primaryExists -and $fallbackExists) {
    $a = Get-Item $primary
    $b = Get-Item $fallback
    if ($b.LastWriteTimeUtc -gt $a.LastWriteTimeUtc) { return $fallback }
    return $primary
  }
  if ($primaryExists) { return $primary }
  if ($fallbackExists) { return $fallback }
  return $primary
}

$CsvPath = Resolve-CanonicalPath $CsvPath
if (-not (Test-Path $CsvPath)) {
  throw "Validation failed: file not found: $CsvPath"
}

$rows = Import-Csv $CsvPath
if (-not $rows) {
  throw "Validation failed: CSV is empty: $CsvPath"
}

$rowCount = $rows.Count
if ($rowCount -lt $MinRows) {
  throw "Validation failed: row count $rowCount is below minimum $MinRows"
}

$requiredColumns = @(
  "Institution", "Program", "Credential_Type", "Status",
  "Min_Avg_Final", "Competitive_Final", "Avg_Total",
  "English_Req", "English_Min", "Math_Req", "Math_Min",
  "Social_Req", "Social_Min", "Science_Req", "Science_Min",
  "Elective_Qty", "Elective_Pool", "Requirement_Type"
)

$headers = Get-HeaderNames $rows
$missingColumns = @($requiredColumns | Where-Object { -not (Has-Column $headers $_) })
if ($missingColumns.Count -gt 0) {
  throw "Validation failed: missing required columns: $($missingColumns -join ', ')"
}

$counts = @($rows | Group-Object Institution | Sort-Object Count -Descending)
$countsMap = @{}
foreach ($g in $counts) { $countsMap[$g.Name] = $g.Count }

foreach ($inst in $RequiredInstitutions) {
  if (-not $countsMap.ContainsKey($inst) -or $countsMap[$inst] -le 0) {
    throw "Validation failed: required institution '$inst' has no rows"
  }
}

$overrideExcludeNameByInst = @{}
$overrideExcludeUrlByInst = @{}
if (Test-Path $ProgramOverridesPath) {
  foreach ($overrideRow in (Import-Csv $ProgramOverridesPath)) {
    $status = Normalize-Text (Get-PropValue -row $overrideRow -names @("status", "Status"))
    if (-not (Is-ActiveOverrideStatus $status)) { continue }

    $includeOrExclude = (Normalize-Text (Get-PropValue -row $overrideRow -names @("include_or_exclude", "Include_Or_Exclude"))).ToLowerInvariant()
    if ($includeOrExclude -ne "exclude") { continue }

    $inst = (Normalize-Text (Get-PropValue -row $overrideRow -names @("institution", "Institution"))).ToLowerInvariant()
    if (-not $inst) { continue }

    $programKey = Normalize-ProgramKey (Get-PropValue -row $overrideRow -names @("program", "Program"))
    if ($programKey) {
      Add-ToNestedSet -map $overrideExcludeNameByInst -instKey $inst -valueKey $programKey
    }

    $sourceUrlKey = Normalize-UrlKey (Get-PropValue -row $overrideRow -names @("source_page_url", "Source_Page_Url"))
    if ($sourceUrlKey) {
      Add-ToNestedSet -map $overrideExcludeUrlByInst -instKey $inst -valueKey $sourceUrlKey
    }
    $parentUrlKey = Normalize-UrlKey (Get-PropValue -row $overrideRow -names @("parent_admissions_url", "Parent_Admissions_Url"))
    if ($parentUrlKey) {
      Add-ToNestedSet -map $overrideExcludeUrlByInst -instKey $inst -valueKey $parentUrlKey
    }
  }
}

$naitSeed = @{}
if (-not (Test-Path $NaitSeedPath)) {
  throw "Validation failed: NAIT seed file not found: $NaitSeedPath"
}
foreach ($seedRow in (Import-Csv $NaitSeedPath)) {
  Add-ToSet -set $naitSeed -key (Normalize-ProgramKey (Get-PropValue -row $seedRow -names @("program_name", "Program")))
}

$norquestSeed = @{}
if (-not (Test-Path $NorquestSeedPath)) {
  throw "Validation failed: NorQuest seed file not found: $NorquestSeedPath"
}
foreach ($seedRow in (Import-Csv $NorquestSeedPath)) {
  Add-ToSet -set $norquestSeed -key (Normalize-ProgramKey (Get-PropValue -row $seedRow -names @("program_name", "Program")))
}

$macewanSeed = @{}
$macewanSeedRowCount = 0
if (-not (Test-Path $MacewanSeedPath)) {
  throw "Validation failed: MacEwan seed file not found: $MacewanSeedPath"
}
foreach ($seedRow in (Import-Csv $MacewanSeedPath)) {
  $nameKey = Normalize-ProgramKey (Get-PropValue -row $seedRow -names @("program_name", "Program"))
  $requirementsUrl = Normalize-Text (Get-PropValue -row $seedRow -names @("requirements_url"))
  $seedProgramUrl = Normalize-Text (Get-PropValue -row $seedRow -names @("program_url_seed", "program_url", "Program_URL", "url"))
  $seedUrl = if ($requirementsUrl) { $requirementsUrl } else { $seedProgramUrl }
  if (-not $nameKey -or -not $seedUrl) { continue }

  $seedUrlKey = Normalize-UrlKey $seedUrl
  $reqUrlKey = Normalize-UrlKey $requirementsUrl
  $programUrlKey = Normalize-UrlKey $seedProgramUrl
  $isExcluded = (In-NestedSet -map $overrideExcludeNameByInst -instKey "macewan" -valueKey $nameKey) -or
    (In-NestedSet -map $overrideExcludeUrlByInst -instKey "macewan" -valueKey $seedUrlKey) -or
    (In-NestedSet -map $overrideExcludeUrlByInst -instKey "macewan" -valueKey $reqUrlKey) -or
    (In-NestedSet -map $overrideExcludeUrlByInst -instKey "macewan" -valueKey $programUrlKey)
  if ($isExcluded) { continue }

  $macewanSeedRowCount++
  Add-ToSet -set $macewanSeed -key $nameKey
}

$ualbertaMap = @{}
$ualbertaMapProgramByKey = @{}
$ualbertaMapRowCount = 0
$ualbertaMapDuplicateNames = @()
$ualbertaMapInvalidUrls = @()
if ($RequireUalbertaMap -and -not (Test-Path $UalbertaMapPath)) {
  throw "Validation failed: UAlberta URL map file not found: $UalbertaMapPath"
}
if (Test-Path $UalbertaMapPath) {
  foreach ($mapRow in (Import-Csv $UalbertaMapPath)) {
    $name = Normalize-Text (Get-PropValue -row $mapRow -names @("program_name", "Program"))
    $nameKey = Normalize-ProgramKey $name
    if (-not $nameKey) { continue }

    $url = Normalize-Text (Get-PropValue -row $mapRow -names @("program_url", "Program_URL", "source_url", "url"))
    if ($ualbertaMap.ContainsKey($nameKey)) {
      $ualbertaMapDuplicateNames += $name
      continue
    }

    $ualbertaMap[$nameKey] = $url
    $ualbertaMapProgramByKey[$nameKey] = $name
    $ualbertaMapRowCount++
    if (-not (Is-HttpUrl $url)) {
      $ualbertaMapInvalidUrls += $name
    }
  }
}
if ($RequireUalbertaMap) {
  if ($ualbertaMapRowCount -eq 0) {
    throw "Validation failed: UAlberta URL map has no rows: $UalbertaMapPath"
  }
  if ($ualbertaMapDuplicateNames.Count -gt 0) {
    $examples = @($ualbertaMapDuplicateNames | Select-Object -First 25) -join "; "
    throw "Validation failed: UAlberta URL map contains duplicate program_name keys ($($ualbertaMapDuplicateNames.Count)). Examples: $examples"
  }
  if ($ualbertaMapInvalidUrls.Count -gt 0) {
    $examples = @($ualbertaMapInvalidUrls | Select-Object -First 25) -join "; "
    throw "Validation failed: UAlberta URL map contains missing/non-http program_url rows ($($ualbertaMapInvalidUrls.Count)). Examples: $examples"
  }
}

$naitLegacyAllowlist = @{}
if (Test-Path $NaitLegacyAllowlistPath) {
  foreach ($allowRow in (Import-Csv $NaitLegacyAllowlistPath)) {
    Add-ToSet -set $naitLegacyAllowlist -key (Normalize-ProgramKey (Get-PropValue -row $allowRow -names @("program_name", "Program")))
  }
}

if (-not (Test-Path $NaitRulesPath)) {
  throw "Validation failed: NAIT rules file not found: $NaitRulesPath"
}
$rulesJson = Get-Content -Raw $NaitRulesPath | ConvertFrom-Json
$blockedUrlPatterns = To-StringArray $rulesJson.blocked_url_patterns
$blockedNamePatterns = To-StringArray $rulesJson.blocked_name_patterns
$evidenceTokens = To-StringArray $rulesJson.evidence_not_program_tokens
if ($evidenceTokens.Count -eq 0) {
  $evidenceTokens = @("not a program page")
}
$allowProgram = @{}
foreach ($name in (To-StringArray $rulesJson.allowlist_program_names)) {
  Add-ToSet -set $allowProgram -key (Normalize-ProgramKey $name)
}
$allowUrl = @{}
foreach ($url in (To-StringArray $rulesJson.allowlist_urls)) {
  Add-ToSet -set $allowUrl -key (Normalize-UrlKey $url)
}

$norquestBlockedUrlPatterns = @()
$norquestBlockedNamePatterns = @()
$norquestEvidenceTokens = @("not a program page")
$norquestAllowProgram = @{}
$norquestAllowUrl = @{}
if (-not (Test-Path $NorquestRulesPath)) {
  throw "Validation failed: NorQuest rules file not found: $NorquestRulesPath"
}
$norquestRulesJson = Get-Content -Raw $NorquestRulesPath | ConvertFrom-Json
$norquestBlockedUrlPatterns = To-StringArray $norquestRulesJson.blocked_url_patterns
$norquestBlockedNamePatterns = To-StringArray $norquestRulesJson.blocked_name_patterns
$norquestEvidenceTokens = To-StringArray $norquestRulesJson.evidence_not_program_tokens
if ($norquestEvidenceTokens.Count -eq 0) {
  $norquestEvidenceTokens = @("not a program page")
}
foreach ($name in (To-StringArray $norquestRulesJson.allowlist_program_names)) {
  Add-ToSet -set $norquestAllowProgram -key (Normalize-ProgramKey $name)
}
foreach ($url in (To-StringArray $norquestRulesJson.allowlist_urls)) {
  Add-ToSet -set $norquestAllowUrl -key (Normalize-UrlKey $url)
}

$naitEvidenceByName = @{}
$norquestEvidenceByName = @{}
if (Test-Path $ProgramEvidencePath) {
  foreach ($e in (Import-Csv $ProgramEvidencePath)) {
    $inst = Normalize-Text (Get-PropValue -row $e -names @("institution", "Institution"))
    $instKey = $inst.ToUpperInvariant()
    if ($instKey -ne "NAIT" -and $instKey -ne "NORQUEST") { continue }
    $nameKey = Normalize-ProgramKey (Get-PropValue -row $e -names @("program_name", "Program"))
    if (-not $nameKey) { continue }
    $notes = Normalize-Text (Get-PropValue -row $e -names @("notes_uncertain", "Notes_Uncertain", "notes", "Notes"))
    if (-not $notes) { continue }
    if ($instKey -eq "NAIT") {
      if ($naitEvidenceByName.ContainsKey($nameKey)) {
        $naitEvidenceByName[$nameKey] = "{0} | {1}" -f $naitEvidenceByName[$nameKey], $notes
      } else {
        $naitEvidenceByName[$nameKey] = $notes
      }
    } else {
      if ($norquestEvidenceByName.ContainsKey($nameKey)) {
        $norquestEvidenceByName[$nameKey] = "{0} | {1}" -f $norquestEvidenceByName[$nameKey], $notes
      } else {
        $norquestEvidenceByName[$nameKey] = $notes
      }
    }
  }
}

$naitViolations = @()
$naitRows = @($rows | Where-Object { $_.Institution -eq "NAIT" })
foreach ($r in $naitRows) {
  $program = Normalize-Text $r.Program
  $programKey = Normalize-ProgramKey $program
  $url = Normalize-Text (Get-PropValue -row $r -names @("Program_URL", "Source_URL", "source_url", "program_url"))
  $urlKey = Normalize-UrlKey $url
  $isAllow = (($programKey -and $allowProgram.ContainsKey($programKey)) -or
    ($urlKey -and $allowUrl.ContainsKey($urlKey)) -or
    ($programKey -and $naitLegacyAllowlist.ContainsKey($programKey)))

  $reason = ""
  $evidenceLow = ""
  if ($programKey -and $naitEvidenceByName.ContainsKey($programKey)) {
    $evidenceLow = ([string]$naitEvidenceByName[$programKey]).ToLowerInvariant()
  }
  foreach ($token in $evidenceTokens) {
    if ($token -and $evidenceLow.Contains($token.ToLowerInvariant())) {
      $reason = "evidence_non_program"
      break
    }
  }

  if (-not $reason) {
    foreach ($pattern in $blockedUrlPatterns) {
      if ($pattern -and $url -match $pattern) {
        $reason = "blocked_url"
        break
      }
    }
  }

  if (-not $reason) {
    foreach ($pattern in $blockedNamePatterns) {
      if ($pattern -and $program -match $pattern) {
        $reason = "blocked_name"
        break
      }
    }
  }

  if (-not $reason -and -not $isAllow) {
    if (-not ($programKey -and $naitSeed.ContainsKey($programKey))) {
      $reason = "not_in_seed"
    }
  }

  if ($reason) {
    $naitViolations += [pscustomobject]@{
      Program = $program
      Reason = $reason
    }
  }
}

if ($naitViolations.Count -gt 0) {
  $groups = @($naitViolations | Group-Object Reason | Sort-Object Name)
  $summary = @($groups | ForEach-Object { "{0}={1}" -f $_.Name, $_.Count }) -join ", "
  $examples = @($naitViolations | Select-Object -First 25 | ForEach-Object { "{0} ({1})" -f $_.Program, $_.Reason }) -join "; "
  throw "Validation failed: NAIT non-program/seed violations found ($summary). Examples: $examples"
}

$norquestViolations = @()
$norquestRows = @($rows | Where-Object { $_.Institution -eq "NorQuest" })
foreach ($r in $norquestRows) {
  $program = Normalize-Text $r.Program
  $programKey = Normalize-ProgramKey $program
  $url = Normalize-Text (Get-PropValue -row $r -names @("Program_URL", "Source_URL", "source_url", "program_url"))
  $urlKey = Normalize-UrlKey $url
  $isAllow = (($programKey -and $norquestAllowProgram.ContainsKey($programKey)) -or
    ($urlKey -and $norquestAllowUrl.ContainsKey($urlKey)))

  $reason = ""
  $evidenceLow = ""
  if ($programKey -and $norquestEvidenceByName.ContainsKey($programKey)) {
    $evidenceLow = ([string]$norquestEvidenceByName[$programKey]).ToLowerInvariant()
  }
  foreach ($token in $norquestEvidenceTokens) {
    if ($token -and $evidenceLow.Contains($token.ToLowerInvariant())) {
      $reason = "evidence_non_program"
      break
    }
  }

  if (-not $reason) {
    foreach ($pattern in $norquestBlockedUrlPatterns) {
      if ($pattern -and $url -match $pattern) {
        $reason = "blocked_url"
        break
      }
    }
  }

  if (-not $reason) {
    foreach ($pattern in $norquestBlockedNamePatterns) {
      if ($pattern -and $program -match $pattern) {
        $reason = "blocked_name"
        break
      }
    }
  }

  if (-not $reason -and -not $isAllow) {
    if (-not ($programKey -and $norquestSeed.ContainsKey($programKey))) {
      $reason = "not_in_seed"
    }
  }

  if ($reason) {
    $norquestViolations += [pscustomobject]@{
      Program = $program
      Reason = $reason
    }
  }
}

if ($norquestViolations.Count -gt 0) {
  $groups = @($norquestViolations | Group-Object Reason | Sort-Object Name)
  $summary = @($groups | ForEach-Object { "{0}={1}" -f $_.Name, $_.Count }) -join ", "
  $examples = @($norquestViolations | Select-Object -First 25 | ForEach-Object { "{0} ({1})" -f $_.Program, $_.Reason }) -join "; "
  throw "Validation failed: NorQuest non-program/seed violations found ($summary). Examples: $examples"
}

$macewanRows = @($rows | Where-Object { $_.Institution -eq "MacEwan" })
if ($macewanRows.Count -ne $macewanSeedRowCount) {
  throw (
    "Validation failed: MacEwan row count mismatch. seed_rows={0}, canonical_rows={1}" -f
    $macewanSeedRowCount, $macewanRows.Count
  )
}

$macewanMissingUrl = @()
$macewanOutOfSeed = @()
$macewanUnresolvedMissingSeeDegree = @()
foreach ($r in $macewanRows) {
  $program = Normalize-Text $r.Program
  $programKey = Normalize-ProgramKey $program
  if (-not ($programKey -and $macewanSeed.ContainsKey($programKey))) {
    $macewanOutOfSeed += $program
  }

  $url = Normalize-Text (Get-PropValue -row $r -names @("Program_URL", "Source_URL", "source_url", "program_url"))
  if (-not (Is-HttpUrl $url)) {
    $macewanMissingUrl += $program
  }

  $hasStructuredSignals = $false
  foreach ($value in @(
      (Normalize-Text $r.Min_Avg_Final),
      (Normalize-Text $r.English_Req),
      (Normalize-Text $r.Math_Req),
      (Normalize-Text $r.Social_Req),
      (Normalize-Text $r.Science_Req),
      (Normalize-Text $r.Elective_Qty)
    )) {
    if ($value) {
      $hasStructuredSignals = $true
      break
    }
  }

  if (-not $hasStructuredSignals) {
    $reqType = Normalize-Text $r.Requirement_Type
    if ($reqType -ne "See Degree") {
      $macewanUnresolvedMissingSeeDegree += $program
    }
  }
}

if ($macewanMissingUrl.Count -gt 0) {
  $examples = @($macewanMissingUrl | Select-Object -First 25) -join "; "
  throw "Validation failed: MacEwan rows missing/non-http Program_URL found ($($macewanMissingUrl.Count)). Examples: $examples"
}

if ($macewanOutOfSeed.Count -gt 0) {
  $examples = @($macewanOutOfSeed | Select-Object -First 25) -join "; "
  throw "Validation failed: MacEwan rows outside seed found ($($macewanOutOfSeed.Count)). Examples: $examples"
}

if ($macewanUnresolvedMissingSeeDegree.Count -gt 0) {
  $examples = @($macewanUnresolvedMissingSeeDegree | Select-Object -First 25) -join "; "
  throw "Validation failed: MacEwan unresolved rows missing Requirement_Type=See Degree ($($macewanUnresolvedMissingSeeDegree.Count)). Examples: $examples"
}

$ualbertaRows = @($rows | Where-Object { $_.Institution -eq "UAlberta" })
if ($RequireUalbertaMap -and ($ualbertaRows.Count -ne $ualbertaMapRowCount)) {
  throw (
    "Validation failed: UAlberta row count mismatch. map_rows={0}, canonical_rows={1}" -f
    $ualbertaMapRowCount, $ualbertaRows.Count
  )
}

$ualbertaMissingUrl = @()
$ualbertaOutOfMap = @()
$ualbertaMismatchedUrl = @()
$ualbertaSeenMapKeys = @{}
foreach ($r in $ualbertaRows) {
  $program = Normalize-Text $r.Program
  $programKey = Normalize-ProgramKey $program
  $url = Normalize-Text (Get-PropValue -row $r -names @("Program_URL", "Source_URL", "source_url", "program_url"))

  if (-not ($programKey -and $ualbertaMap.ContainsKey($programKey))) {
    $ualbertaOutOfMap += $program
  } else {
    Add-ToSet -set $ualbertaSeenMapKeys -key $programKey
    $expectedUrl = Normalize-Text $ualbertaMap[$programKey]
    if ((Is-HttpUrl $url) -and (Is-HttpUrl $expectedUrl)) {
      if ((Normalize-UrlKey $url) -ne (Normalize-UrlKey $expectedUrl)) {
        $ualbertaMismatchedUrl += ("{0} (expected: {1} | got: {2})" -f $program, $expectedUrl, $url)
      }
    }
  }

  if (-not (Is-HttpUrl $url)) {
    $ualbertaMissingUrl += $program
  }
}

if ($RequireUalbertaMap -and $ualbertaOutOfMap.Count -gt 0) {
  $examples = @($ualbertaOutOfMap | Select-Object -First 25) -join "; "
  throw "Validation failed: UAlberta rows outside URL map found ($($ualbertaOutOfMap.Count)). Examples: $examples"
}

if ($ualbertaMissingUrl.Count -gt 0) {
  $examples = @($ualbertaMissingUrl | Select-Object -First 25) -join "; "
  throw "Validation failed: UAlberta rows missing/non-http Program_URL found ($($ualbertaMissingUrl.Count)). Examples: $examples"
}

if ($RequireUalbertaMap -and $ualbertaMismatchedUrl.Count -gt 0) {
  $examples = @($ualbertaMismatchedUrl | Select-Object -First 25) -join "; "
  throw "Validation failed: UAlberta Program_URL mismatch vs URL map ($($ualbertaMismatchedUrl.Count)). Examples: $examples"
}

if ($RequireUalbertaMap) {
  $mapMissingFromCanonical = @()
  foreach ($key in $ualbertaMap.Keys) {
    if ($ualbertaSeenMapKeys.ContainsKey($key)) { continue }
    $mapMissingFromCanonical += (Normalize-Text $ualbertaMapProgramByKey[$key])
  }
  if ($mapMissingFromCanonical.Count -gt 0) {
    $examples = @($mapMissingFromCanonical | Select-Object -First 25) -join "; "
    throw "Validation failed: UAlberta URL map rows missing from canonical ($($mapMissingFromCanonical.Count)). Examples: $examples"
  }
}

if (Test-Path $BaselinePath) {
  $baselineRows = Import-Csv $BaselinePath
  if ($baselineRows -and $baselineRows.Count -gt 0) {
    $baselineCount = [double]$baselineRows.Count
    $dropPercent = ((($baselineCount - [double]$rowCount) / $baselineCount) * 100)
    if ($dropPercent -gt $MaxRowDropPercent) {
      $baselineHeaders = Get-HeaderNames $baselineRows
      $canCheckNaitOnlyShrink = (Has-Column $baselineHeaders "Institution") -and $countsMap.ContainsKey("NAIT")
      if ($canCheckNaitOnlyShrink) {
        $baselineNait = @($baselineRows | Where-Object { $_.Institution -eq "NAIT" }).Count
        $baselineNonNait = [double]$baselineRows.Count - [double]$baselineNait
        $currentNait = [double]$countsMap["NAIT"]
        $currentNonNait = [double]$rowCount - $currentNait

        $nonNaitDropPercent = 0.0
        if ($baselineNonNait -gt 0) {
          $nonNaitDropPercent = ((($baselineNonNait - $currentNonNait) / $baselineNonNait) * 100)
        }

        if ($nonNaitDropPercent -le $MaxRowDropPercent) {
          Write-Warning ("Row count drop {0}% exceeds max {1}% but appears NAIT-driven (baseline NAIT={2}, current NAIT={3}; non-NAIT drop={4}%)." -f
            [math]::Round($dropPercent, 2), $MaxRowDropPercent, $baselineNait, $currentNait, [math]::Round($nonNaitDropPercent, 2))
        } else {
          throw "Validation failed: row count dropped by $([math]::Round($dropPercent,2))% (baseline=$baselineCount, current=$rowCount, max=$MaxRowDropPercent%)"
        }
      } else {
        throw "Validation failed: row count dropped by $([math]::Round($dropPercent,2))% (baseline=$baselineCount, current=$rowCount, max=$MaxRowDropPercent%)"
      }
    }
  }
}

$dupGroups = @($rows | Group-Object Institution, Program, Credential_Type, Status | Where-Object { $_.Count -gt 1 })
if ($dupGroups.Count -gt 0) {
  Write-Warning "Validation warning: found $($dupGroups.Count) duplicate key groups (Institution+Program+Credential_Type+Status)."
}

Write-Host "Validation passed: $rowCount rows in $CsvPath"
Write-Host "Institution counts:"
foreach ($g in $counts) {
  Write-Host "  $($g.Name): $($g.Count)"
}
Write-Host ("NAIT seed/rules check passed: {0} rows checked, seed size {1}, legacy allowlist size {2}" -f
  $naitRows.Count, $naitSeed.Count, $naitLegacyAllowlist.Count)
Write-Host ("NorQuest seed/rules check passed: {0} rows checked, seed size {1}" -f
  $norquestRows.Count, $norquestSeed.Count)
Write-Host ("MacEwan seed checks passed: {0} rows checked, seed rows {1}, unique seed names {2}" -f
  $macewanRows.Count, $macewanSeedRowCount, $macewanSeed.Count)
Write-Host ("UAlberta URL map checks passed: {0} rows checked, map rows {1}" -f
  $ualbertaRows.Count, $ualbertaMapRowCount)
