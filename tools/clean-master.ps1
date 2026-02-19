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
    Add-ToSet -set $naitSeedNames -key (Normalize-ProgramKey $seed.program_name)
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

if ($DropNaitNonPrograms -or $DropNorQuestNonPrograms) {
  $rows = $rows | Where-Object {
    $inst = Normalize-Text $_.Institution
    $programName = Normalize-Text $_.Program
    $programKey = Normalize-ProgramKey $programName
    $programUrl = Get-RowProgramUrl $_
    $programUrlKey = Normalize-UrlKey $programUrl

    if ($inst -eq "NAIT" -and $DropNaitNonPrograms) {
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

      if ($programKey -and $naitLegacyAllowlistNames.ContainsKey($programKey)) {
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
    Avg_Total            = "" # to be populated by scrape/extract pipeline (or AvgRules sheet)

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
    $backfillRows += [pscustomobject]@{
      Institution          = "NorQuest"
      Program              = $seedRow.Program
      Credential_Type      = (Normalize-NorquestCredentialType $seedRow.Credential_Type)
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
    $norquestStats.seed_backfill_added = $backfillRows.Count
    $canonical = @($canonical) + @($backfillRows)
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

  if ($MacewanRequireFullSeedCoverage -and ($rebuiltMacewanRows.Count -ne $macewanSeedRows.Count)) {
    throw (
      "MacEwan seed coverage mismatch: expected {0} rows, rebuilt {1}" -f
      $macewanSeedRows.Count, $rebuiltMacewanRows.Count
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
