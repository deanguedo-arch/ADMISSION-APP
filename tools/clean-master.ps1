param(
  [string]$InputPath = ".\\ALBERTA_ADMISSIONS_MASTER_FINAL_v3.csv",
  [string]$OutputPath = ".\\data\\ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv",
  [string]$ProgramEvidencePath = ".\\PROGRAMS_ONLY.csv",
  [string]$FilterRulesPath = ".\\config\\nait_non_program_rules.json",
  [string]$NaitSeedPath = ".\\pipeline\\nait_program_seed.csv",
  [string]$NaitLegacyAllowlistPath = ".\\config\\nait_legacy_allowlist.csv",
  [switch]$DropNaitNonPrograms = $true,
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

if (Test-Path $NaitSeedPath) {
  foreach ($seed in (Import-Csv $NaitSeedPath)) {
    Add-ToSet -set $naitSeedNames -key (Normalize-ProgramKey $seed.program_name)
  }
}

if (Test-Path $NaitLegacyAllowlistPath) {
  foreach ($allow in (Import-Csv $NaitLegacyAllowlistPath)) {
    $name = Normalize-ProgramKey (Get-PropValue -row $allow -names @("program_name", "Program"))
    Add-ToSet -set $naitLegacyAllowlistNames -key $name
  }
}

if (Test-Path $ProgramEvidencePath) {
  foreach ($e in (Import-Csv $ProgramEvidencePath)) {
    $inst = Normalize-Text (Get-PropValue -row $e -names @("institution", "Institution"))
    if ($inst.ToUpperInvariant() -ne "NAIT") { continue }
    $name = Normalize-ProgramKey (Get-PropValue -row $e -names @("program_name", "Program"))
    if (-not $name) { continue }
    $notes = Normalize-Text (Get-PropValue -row $e -names @("notes_uncertain", "Notes_Uncertain", "notes", "Notes"))
    if (-not $notes) { continue }
    if ($naitEvidenceByName.ContainsKey($name)) {
      $naitEvidenceByName[$name] = "{0} | {1}" -f $naitEvidenceByName[$name], $notes
    } else {
      $naitEvidenceByName[$name] = $notes
    }
  }
}

if ($DropNaitNonPrograms) {
  $rows = $rows | Where-Object {
    if ($_.Institution -ne "NAIT") { return $true }
    $naitStats.nait_rows_examined++

    $programName = Normalize-Text $_.Program
    $programKey = Normalize-ProgramKey $programName
    $programUrl = Get-RowProgramUrl $_
    $programUrlKey = Normalize-UrlKey $programUrl

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

if ($DropExactDuplicates) {
  $canonical = $canonical | Sort-Object * -Unique
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
