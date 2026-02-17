param(
  [string]$IndexPath = ".\\pipeline\\program_index.cleaned.csv",
  [string]$CanonicalPath = ".\\data\\ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv",
  [string]$CanonicalFallbackPath = ".\\data\\ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv.new",
  [double]$MinFuzzyScore = 0.55,
  [double]$MinFuzzyGap = 0.08,
  [switch]$AllowOverwriteExisting,
  [switch]$DryRun,
  [string]$AuditOutPath = ".\\out\\ProgramUrlMapping.audit.csv"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Is-Blank([object]$v) {
  return ($null -eq $v) -or [string]::IsNullOrWhiteSpace([string]$v)
}

function Normalize-Text([object]$v) {
  if (Is-Blank $v) { return "" }
  $s = ([string]$v).Trim()
  if ($s -match "^(?i:nan|none|null)$") { return "" }
  return $s
}

function Normalize-ProgramText([object]$v) {
  $s = Normalize-Text $v
  if (Is-Blank $s) { return "" }
  $t = $s.ToLowerInvariant()
  $t = [regex]::Replace($t, "\(.*?\)", " ")
  $t = [regex]::Replace($t, "[\u2010-\u2015]", " ")
  $t = [regex]::Replace($t, "[^a-z0-9 ]", " ")
  $t = [regex]::Replace($t, "\s+", " ").Trim()
  return $t
}

function Get-Tokens([string]$text) {
  $n = Normalize-ProgramText $text
  if (Is-Blank $n) { return @() }
  return @($n.Split(" ") | Where-Object { -not (Is-Blank $_) } | Sort-Object -Unique)
}

function Score-Jaccard([string[]]$a, [string[]]$b) {
  if (-not $a -or -not $b) { return 0.0 }
  $setA = @{}
  foreach ($x in @($a)) {
    if (Is-Blank $x) { continue }
    $setA[$x] = $true
  }
  $setB = @{}
  foreach ($x in @($b)) {
    if (Is-Blank $x) { continue }
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

function Resolve-CanonicalPath([string]$canonicalPath, [string]$fallbackPath) {
  $canonicalExists = Test-Path $canonicalPath
  $fallbackExists = Test-Path $fallbackPath

  if ($canonicalExists -and $fallbackExists) {
    $a = Get-Item $canonicalPath
    $b = Get-Item $fallbackPath
    if ($b.LastWriteTimeUtc -gt $a.LastWriteTimeUtc) { return $fallbackPath }
    return $canonicalPath
  }
  if ($canonicalExists) { return $canonicalPath }
  if ($fallbackExists) { return $fallbackPath }
  throw "Could not find canonical CSV at $canonicalPath or $fallbackPath"
}

function Ensure-Dir([string]$path) {
  $dir = Split-Path -Parent $path
  if (-not (Test-Path $dir)) {
    New-Item -ItemType Directory -Path $dir | Out-Null
  }
}

function Build-Key([string]$institution, [string]$program, [string]$credential) {
  return "{0}||{1}||{2}" -f $institution.ToLowerInvariant(), $program.ToLowerInvariant(), $credential.ToLowerInvariant()
}

function Is-HttpUrl([string]$url) {
  $u = Normalize-Text $url
  if (Is-Blank $u) { return $false }
  return ($u -match "^(?i:https?)://")
}

function Credential-Class([string]$credential) {
  $c = Normalize-Text $credential
  if (Is-Blank $c) { return "other" }
  $t = $c.ToLowerInvariant()
  if ($t -match "bachelor|degree") { return "degree" }
  if ($t -match "diploma") { return "diploma" }
  if ($t -match "certificate") { return "certificate" }
  if ($t -match "minor") { return "minor" }
  return "other"
}

function Credential-Bonus([string]$canonicalClass, [string]$indexClass) {
  if (Is-Blank $canonicalClass -or $canonicalClass -eq "other") { return 0.0 }
  if (Is-Blank $indexClass -or $indexClass -eq "other") { return 0.0 }
  if ($canonicalClass -eq $indexClass) { return 0.05 }
  return -0.04
}

function Add-ToBucket([hashtable]$map, [string]$key, [object]$value) {
  if (-not $map.ContainsKey($key)) { $map[$key] = @() }
  $map[$key] = @($map[$key]) + $value
}

function Get-UniqueHttpUrls([object[]]$entries) {
  $urls = @(
    @($entries) |
      ForEach-Object {
        if ($_ -is [string]) {
          Normalize-Text $_
        } elseif ($null -eq $_) {
          ""
        } else {
          $prop = $_.PSObject.Properties["source_url"]
          if ($null -eq $prop) {
            ""
          } else {
            Normalize-Text $prop.Value
          }
        }
      } |
      Where-Object { Is-HttpUrl $_ } |
      Sort-Object -Unique
  )
  return $urls
}

if (-not (Test-Path $IndexPath)) {
  throw "Index file not found: $IndexPath"
}

$canonicalSourcePath = Resolve-CanonicalPath -canonicalPath $CanonicalPath -fallbackPath $CanonicalFallbackPath
if (-not (Test-Path $canonicalSourcePath)) {
  throw "Canonical CSV not found: $canonicalSourcePath"
}

$canonicalRows = @(Import-Csv $canonicalSourcePath)
if ($canonicalRows.Count -eq 0) {
  throw "Canonical CSV is empty: $canonicalSourcePath"
}

$indexRowsRaw = @(Import-Csv $IndexPath)
if ($indexRowsRaw.Count -eq 0) {
  throw "Index CSV is empty: $IndexPath"
}

if ($null -eq $canonicalRows[0].PSObject.Properties["Program_URL"]) {
  foreach ($row in $canonicalRows) {
    Add-Member -InputObject $row -NotePropertyName "Program_URL" -NotePropertyValue ""
  }
}

$indexRows = @()
foreach ($r in $indexRowsRaw) {
  $institution = Normalize-Text $r.institution
  $programName = Normalize-Text $r.program_name
  $normProgramName = Normalize-ProgramText $programName
  $credential = Normalize-Text $r.credential
  $credentialClass = Credential-Class $credential
  $sourceUrl = Normalize-Text $r.source_url
  if (Is-Blank $institution -or Is-Blank $programName -or Is-Blank $normProgramName -or -not (Is-HttpUrl $sourceUrl)) { continue }

  $indexRows += [pscustomobject]@{
    institution = $institution
    program_name = $programName
    credential = $credential
    source_url = $sourceUrl
    key_full = Build-Key -institution $institution -program $normProgramName -credential $credentialClass
    key_program = Build-Key -institution $institution -program $normProgramName -credential ""
    norm_program = $normProgramName
    tokens = Get-Tokens $programName
    credential_class = $credentialClass
  }
}

if ($indexRows.Count -eq 0) {
  throw "No valid index rows with program URLs were found in $IndexPath"
}

$indexByFullKey = @{}
$indexByProgramKey = @{}
$indexByInstitution = @{}
foreach ($row in $indexRows) {
  Add-ToBucket -map $indexByFullKey -key $row.key_full -value $row
  Add-ToBucket -map $indexByProgramKey -key $row.key_program -value $row
  Add-ToBucket -map $indexByInstitution -key $row.institution.ToLowerInvariant() -value $row
}

$auditRows = @()
$filled = 0
$overwritten = 0
$keptExisting = 0
$ambiguous = 0
$unmatched = 0
$invalidExisting = 0
$skippedBlankProgram = 0
$mappedByMethod = @{
  exact_full = 0
  exact_program_credential = 0
  exact_program = 0
  fuzzy_unique_name = 0
  fuzzy_unique_url = 0
}

for ($i = 0; $i -lt $canonicalRows.Count; $i++) {
  $row = $canonicalRows[$i]
  $institution = Normalize-Text $row.Institution
  $program = Normalize-Text $row.Program
  $credential = Normalize-Text $row.Credential_Type
  $existingUrl = Normalize-Text $row.Program_URL
  $existingIsValid = Is-HttpUrl $existingUrl

  $mappingStatus = ""
  $mappingMethod = ""
  $matchScore = ""
  $candidateCount = 0
  $notes = ""
  $resolvedUrl = ""

  if (Is-Blank $institution -or Is-Blank $program) {
    $skippedBlankProgram++
    $mappingStatus = "skipped_blank_key"
    $notes = "Missing institution or program"
  } elseif (-not $AllowOverwriteExisting -and -not (Is-Blank $existingUrl)) {
    $keptExisting++
    if (-not $existingIsValid) { $invalidExisting++ }
    $mappingStatus = "kept_existing"
    $mappingMethod = "existing"
    $resolvedUrl = $existingUrl
  } else {
    $normProgram = Normalize-ProgramText $program
    if (Is-Blank $normProgram) {
      $unmatched++
      $mappingStatus = "no_match"
      $notes = "Program name normalized to empty"
      $auditRows += [pscustomobject]@{
        Institution = $institution
        Program = $program
        Credential_Type = $credential
        Previous_Program_URL = $existingUrl
        Final_Program_URL = Normalize-Text $row.Program_URL
        Mapping_Status = $mappingStatus
        Mapping_Method = $mappingMethod
        Match_Score = $matchScore
        Candidate_Count = $candidateCount
        Notes = $notes
      }
      continue
    }

    $canonicalCredentialClass = Credential-Class $credential
    $fullKey = Build-Key -institution $institution -program $normProgram -credential $canonicalCredentialClass
    $programKey = Build-Key -institution $institution -program $normProgram -credential ""
    $instKey = $institution.ToLowerInvariant()

    $fullCandidates = @($(if ($indexByFullKey.ContainsKey($fullKey)) { $indexByFullKey[$fullKey] } else { @() }))
    $fullUrls = Get-UniqueHttpUrls $fullCandidates
    $candidateCount = @($fullCandidates).Count

    if (@($fullUrls).Count -eq 1) {
      $resolvedUrl = @($fullUrls)[0]
      $mappingMethod = "exact_full"
      $mappingStatus = "mapped"
    } else {
      $programCandidates = @($(if ($indexByProgramKey.ContainsKey($programKey)) { $indexByProgramKey[$programKey] } else { @() }))
      if (@($programCandidates).Count -gt 0) { $candidateCount = @($programCandidates).Count }
      $programUrls = Get-UniqueHttpUrls $programCandidates

      if (@($programUrls).Count -eq 1) {
        $resolvedUrl = @($programUrls)[0]
        $mappingMethod = "exact_program"
        $mappingStatus = "mapped"
      } else {
        $programCandidatesCred = @($(if ($canonicalCredentialClass -eq "other") { @() } else {
          @($programCandidates | Where-Object { $_.credential_class -eq $canonicalCredentialClass })
        }))
        $programUrlsCred = Get-UniqueHttpUrls $programCandidatesCred

        if (@($programUrlsCred).Count -eq 1) {
          $resolvedUrl = @($programUrlsCred)[0]
          $mappingMethod = "exact_program_credential"
          $mappingStatus = "mapped"
        } else {
          $fuzzyPool = @($(if ($indexByInstitution.ContainsKey($instKey)) { $indexByInstitution[$instKey] } else { @() }))
          $baseTokens = Get-Tokens $program
          $scored = @()

          if (@($baseTokens).Count -gt 0 -and @($fuzzyPool).Count -gt 0) {
            foreach ($entry in $fuzzyPool) {
              $baseScore = Score-Jaccard -a $baseTokens -b @($entry.tokens)
              if ($baseScore -le 0) { continue }
              $score = $baseScore + (Credential-Bonus -canonicalClass $canonicalCredentialClass -indexClass $entry.credential_class)
              $scored += [pscustomobject]@{
                score = $score
                baseScore = $baseScore
                norm_program = $entry.norm_program
                source_url = $entry.source_url
                credential = $entry.credential
              }
            }
          }

          if (@($scored).Count -eq 0) {
            $mappingStatus = "no_match"
            $notes = "No fuzzy candidates"
          } else {
            $scored = @($scored | Sort-Object @{ Expression = "score"; Descending = $true }, @{ Expression = "baseScore"; Descending = $true })
            $best = $scored[0]
            $bestScore = [double]$best.score
            $matchScore = "{0:N3}" -f $bestScore
            $candidateCount = @($scored).Count

            if ($bestScore -lt $MinFuzzyScore) {
              $mappingStatus = "no_match"
              $notes = "Top fuzzy score below threshold"
            } else {
              $near = @($scored | Where-Object { ($bestScore - [double]$_.score) -lt $MinFuzzyGap })
              $distinctNearNames = @($near | Select-Object -ExpandProperty norm_program -Unique)
              if (@($distinctNearNames).Count -le 1) {
                $resolvedUrl = Normalize-Text $best.source_url
                $mappingMethod = "fuzzy_unique_name"
                $mappingStatus = "mapped"
              } else {
                $nearUrls = @($near | Select-Object -ExpandProperty source_url -Unique)
                if (@($nearUrls).Count -eq 1) {
                  $resolvedUrl = Normalize-Text @($nearUrls)[0]
                  $mappingMethod = "fuzzy_unique_url"
                  $mappingStatus = "mapped"
                } else {
                  $mappingStatus = "ambiguous"
                  $notes = "Fuzzy tie between distinct program names"
                }
              }
            }
          }
        }
      }
    }

    if ($mappingStatus -eq "mapped" -and -not (Is-HttpUrl $resolvedUrl)) {
      $mappingStatus = "no_match"
      $notes = "Resolved URL was not valid http/https"
      $mappingMethod = ""
      $resolvedUrl = ""
    }

    if ($mappingStatus -eq "mapped") {
      if ($mappingMethod -and $mappedByMethod.ContainsKey($mappingMethod)) {
        $mappedByMethod[$mappingMethod] = [int]$mappedByMethod[$mappingMethod] + 1
      }

      $previous = $existingUrl
      if (Is-Blank $previous) {
        $row.Program_URL = $resolvedUrl
        $filled++
      } elseif ($AllowOverwriteExisting -and $previous -ne $resolvedUrl) {
        $row.Program_URL = $resolvedUrl
        $overwritten++
      } else {
        $keptExisting++
        $mappingStatus = "kept_existing"
      }
    } elseif ($mappingStatus -eq "ambiguous") {
      $ambiguous++
    } elseif ($mappingStatus -eq "no_match") {
      if (-not (Is-Blank $existingUrl)) {
        $keptExisting++
        $mappingStatus = "kept_existing"
      } else {
        $unmatched++
      }
    }
  }

  $auditRows += [pscustomobject]@{
    Institution = $institution
    Program = $program
    Credential_Type = $credential
    Previous_Program_URL = $existingUrl
    Final_Program_URL = Normalize-Text $row.Program_URL
    Mapping_Status = $mappingStatus
    Mapping_Method = $mappingMethod
    Match_Score = $matchScore
    Candidate_Count = $candidateCount
    Notes = $notes
  }
}

Write-Host "Canonical source: $canonicalSourcePath"
Write-Host "Index source: $IndexPath"
Write-Host "Rows scanned: $($canonicalRows.Count)"
Write-Host ("Mapped (filled): {0}" -f $filled)
Write-Host ("Mapped (overwritten): {0}" -f $overwritten)
Write-Host ("Kept existing: {0}" -f $keptExisting)
Write-Host ("Ambiguous: {0}" -f $ambiguous)
Write-Host ("No match: {0}" -f $unmatched)
Write-Host ("Invalid existing URLs: {0}" -f $invalidExisting)
Write-Host ("Skipped blank key rows: {0}" -f $skippedBlankProgram)
Write-Host ("Method breakdown: exact_full={0}, exact_program_credential={1}, exact_program={2}, fuzzy_unique_name={3}, fuzzy_unique_url={4}" -f
  $mappedByMethod.exact_full, $mappedByMethod.exact_program_credential, $mappedByMethod.exact_program, $mappedByMethod.fuzzy_unique_name, $mappedByMethod.fuzzy_unique_url)

Ensure-Dir $AuditOutPath
$auditRows | Export-Csv -NoTypeInformation -Encoding UTF8 $AuditOutPath
Write-Host "Wrote audit -> $AuditOutPath"

if ($DryRun) {
  Write-Host "Dry run only. No canonical file written."
  return
}

if (($filled + $overwritten) -eq 0) {
  Write-Host "No Program_URL changes to write."
  return
}

$targetPath = $canonicalSourcePath
Ensure-Dir $targetPath
$csvLines = $canonicalRows | ConvertTo-Csv -NoTypeInformation
$tmpPath = "$targetPath.tmp"
[System.IO.File]::WriteAllLines($tmpPath, $csvLines, [System.Text.UTF8Encoding]::new($false))

$finalPath = $targetPath
try {
  Move-Item -Force -LiteralPath $tmpPath -Destination $targetPath
} catch {
  $fallback = if ($targetPath -ieq $CanonicalPath) { $CanonicalFallbackPath } else { "$targetPath.new" }
  Move-Item -Force -LiteralPath $tmpPath -Destination $fallback
  $finalPath = $fallback
  Write-Warning "Could not overwrite $targetPath (file in use). Wrote: $fallback"
}

Write-Host "Wrote updated canonical CSV -> $finalPath"
