param(
  [string]$CandidatesPath = ".\\pipeline_artifacts\\extract\\avg_total_candidates.csv",
  [string]$CanonicalPath = ".\\data\\ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv",
  [string]$CanonicalFallbackPath = ".\\data\\ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv.new",
  [string[]]$AllowedConfidence = @("high", "medium"),
  [switch]$IncludeLowConfidence,
  [switch]$AllowOverwriteExisting,
  [switch]$DryRun
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

function Normalize-Confidence([object]$v) {
  $s = Normalize-Text $v
  if (Is-Blank $s) { return "" }
  return $s.ToLowerInvariant()
}

function Try-ParsePositiveInt([object]$v) {
  $s = Normalize-Text $v
  if (Is-Blank $s) { return $null }
  $n = 0
  if ([int]::TryParse($s, [ref]$n) -and $n -gt 0) { return $n }
  return $null
}

function Ensure-Dir([string]$path) {
  $dir = Split-Path -Parent $path
  if (-not (Test-Path $dir)) {
    New-Item -ItemType Directory -Path $dir | Out-Null
  }
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

function Make-Key([string]$institution, [string]$program, [string]$credential) {
  return "{0}||{1}||{2}" -f $institution.ToLowerInvariant(), $program.ToLowerInvariant(), $credential.ToLowerInvariant()
}

function Add-ToIndex([hashtable]$index, [string]$key, [int]$rowIndex) {
  if ($index.ContainsKey($key)) {
    $index[$key] = @($index[$key]) + $rowIndex
    return
  }
  $index[$key] = @($rowIndex)
}

if (-not (Test-Path $CandidatesPath)) {
  throw "Candidates file not found: $CandidatesPath"
}

$canonicalSourcePath = Resolve-CanonicalPath -canonicalPath $CanonicalPath -fallbackPath $CanonicalFallbackPath

$canonicalRows = @(Import-Csv $canonicalSourcePath)
if ($canonicalRows.Count -eq 0) {
  throw "Canonical CSV is empty: $canonicalSourcePath"
}

$candidates = @(Import-Csv $CandidatesPath)
if ($candidates.Count -eq 0) {
  throw "Candidates CSV is empty: $CandidatesPath"
}

$allowed = @(
  $AllowedConfidence |
    ForEach-Object { Normalize-Confidence $_ } |
    Where-Object { -not (Is-Blank $_) } |
    Sort-Object -Unique
)
if ($IncludeLowConfidence -and -not ($allowed -contains "low")) {
  $allowed = @($allowed) + "low"
}
if ($allowed.Count -eq 0) {
  throw "Allowed confidence list is empty after normalization."
}

$fullIndex = @{}
$programIndex = @{}
for ($i = 0; $i -lt $canonicalRows.Count; $i++) {
  $row = $canonicalRows[$i]
  $inst = Normalize-Text $row.Institution
  $prog = Normalize-Text $row.Program
  if ((Is-Blank $inst) -or (Is-Blank $prog)) { continue }
  $cred = Normalize-Text $row.Credential_Type

  $fullKey = Make-Key -institution $inst -program $prog -credential $cred
  $programKey = Make-Key -institution $inst -program $prog -credential ""
  Add-ToIndex -index $fullIndex -key $fullKey -rowIndex $i
  Add-ToIndex -index $programIndex -key $programKey -rowIndex $i
}

$candidateGroups = @{}
$skippedErrors = 0
$skippedNoAvg = 0
$skippedConfidence = 0
$skippedMissingKeys = 0

foreach ($c in $candidates) {
  if (-not (Is-Blank $c.error)) {
    $skippedErrors++
    continue
  }

  $avgTotal = Try-ParsePositiveInt $c.avg_total
  if ($null -eq $avgTotal) {
    $skippedNoAvg++
    continue
  }

  $confidence = Normalize-Confidence $c.avg_total_confidence
  if (-not ($allowed -contains $confidence)) {
    $skippedConfidence++
    continue
  }

  $inst = Normalize-Text $c.institution
  $prog = Normalize-Text $c.program_name
  if ((Is-Blank $inst) -or (Is-Blank $prog)) {
    $skippedMissingKeys++
    continue
  }

  $cred = Normalize-Text $c.credential
  $key = Make-Key -institution $inst -program $prog -credential $cred
  $entry = [pscustomobject]@{
    institution = $inst
    program = $prog
    credential = $cred
    avg_total = $avgTotal
    confidence = $confidence
    rule = Normalize-Text $c.avg_total_rule
    adapter = Normalize-Text $c.avg_total_adapter
    source_url = Normalize-Text $c.source_url
  }

  if ($candidateGroups.ContainsKey($key)) {
    $candidateGroups[$key] = @($candidateGroups[$key]) + $entry
  } else {
    $candidateGroups[$key] = @($entry)
  }
}

$applied = 0
$overwritten = 0
$skippedCandidateConflicts = 0
$skippedNoMatch = 0
$skippedAmbiguous = 0
$skippedExistingDiff = 0
$alreadySame = 0
$changes = @()

foreach ($groupKey in ($candidateGroups.Keys | Sort-Object)) {
  $group = @($candidateGroups[$groupKey])
  $uniqueAvg = @($group | Select-Object -ExpandProperty avg_total -Unique)
  if ($uniqueAvg.Count -ne 1) {
    $skippedCandidateConflicts++
    continue
  }

  $candidate = $group[0]
  $inst = $candidate.institution
  $prog = $candidate.program
  $cred = $candidate.credential
  $avgTotal = [int]$uniqueAvg[0]
  $programKey = Make-Key -institution $inst -program $prog -credential ""

  $matches = @()
  if (-not (Is-Blank $cred)) {
    $fullKey = Make-Key -institution $inst -program $prog -credential $cred
    if ($fullIndex.ContainsKey($fullKey)) {
      $matches = @($fullIndex[$fullKey])
    }
    if ($matches.Count -eq 0 -and $programIndex.ContainsKey($programKey)) {
      $fallback = @($programIndex[$programKey])
      if ($fallback.Count -eq 1) {
        $matches = $fallback
      }
    }
  } else {
    if ($programIndex.ContainsKey($programKey)) {
      $matches = @($programIndex[$programKey])
    }
  }

  if ($matches.Count -eq 0) {
    $skippedNoMatch++
    continue
  }
  if ($matches.Count -gt 1) {
    $skippedAmbiguous++
    continue
  }

  $idx = [int]$matches[0]
  $target = $canonicalRows[$idx]
  $existing = Try-ParsePositiveInt $target.Avg_Total
  if ($null -ne $existing) {
    if ($existing -eq $avgTotal) {
      $alreadySame++
      continue
    }
    if (-not $AllowOverwriteExisting) {
      $skippedExistingDiff++
      continue
    }

    $target.Avg_Total = [string]$avgTotal
    $overwritten++
    $changes += [pscustomobject]@{
      Institution = $target.Institution
      Program = $target.Program
      Credential_Type = $target.Credential_Type
      Prev_Avg_Total = [string]$existing
      New_Avg_Total = [string]$avgTotal
      Mode = "overwrite"
      Confidence = $candidate.confidence
      Rule = $candidate.rule
      Adapter = $candidate.adapter
    }
    continue
  }

  $target.Avg_Total = [string]$avgTotal
  $applied++
  $changes += [pscustomobject]@{
    Institution = $target.Institution
    Program = $target.Program
    Credential_Type = $target.Credential_Type
    Prev_Avg_Total = ""
    New_Avg_Total = [string]$avgTotal
    Mode = "fill"
    Confidence = $candidate.confidence
    Rule = $candidate.rule
    Adapter = $candidate.adapter
  }
}

Write-Host "Canonical source: $canonicalSourcePath"
Write-Host "Candidates loaded: $($candidates.Count)"
Write-Host "Filtered candidates: $($candidateGroups.Count) groups (confidence: $($allowed -join ', '))"
Write-Host "Skipped before matching: errors=$skippedErrors, no_avg=$skippedNoAvg, confidence=$skippedConfidence, missing_keys=$skippedMissingKeys"
Write-Host "Match/apply summary: filled=$applied, overwritten=$overwritten, already_same=$alreadySame, no_match=$skippedNoMatch, ambiguous=$skippedAmbiguous, candidate_conflicts=$skippedCandidateConflicts, existing_diff=$skippedExistingDiff"

if ($changes.Count -gt 0) {
  Write-Host ""
  Write-Host "Changes:"
  $changes | Sort-Object Institution, Program | Format-Table -AutoSize | Out-Host
}

if ($DryRun) {
  Write-Host ""
  Write-Host "Dry run only. No files written."
  return
}

if (($applied + $overwritten) -eq 0) {
  Write-Host ""
  Write-Host "No changes to write."
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

Write-Host ""
Write-Host "Wrote updated canonical CSV -> $finalPath"
