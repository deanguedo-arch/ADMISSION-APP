param(
  [string]$CandidatesPath = ".\pipeline_artifacts\extract\program_field_candidates.csv",
  [string]$CanonicalPath = ".\data\ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv",
  [string]$CanonicalFallbackPath = ".\data\ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv.new",
  [string]$IssuePackPath = ".\scraper_lab\issue_pack.csv",
  [string[]]$AllowedConfidence = @("high", "medium"),
  [switch]$IncludeLowConfidence,
  [switch]$AllowOverwriteExisting,
  [string]$Profile = "candidate",
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

function Normalize-Token([object]$v) {
  return (Normalize-Text $v).ToLowerInvariant()
}

function Normalize-Confidence([object]$v) {
  return Normalize-Token $v
}

function Normalize-Url([object]$v) {
  $s = Normalize-Token $v
  if (Is-Blank $s) { return "" }
  return $s.TrimEnd("/")
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
  return "{0}||{1}||{2}" -f (Normalize-Token $institution), (Normalize-Token $program), (Normalize-Token $credential)
}

function Make-IdentityKey([string]$institution, [string]$program, [string]$credential, [string]$url) {
  return "{0}||{1}||{2}||{3}" -f (Normalize-Token $institution), (Normalize-Token $program), (Normalize-Token $credential), (Normalize-Url $url)
}

function Add-ToIndex([hashtable]$index, [string]$key, [int]$rowIndex) {
  if ($index.ContainsKey($key)) {
    $index[$key] = @($index[$key]) + $rowIndex
    return
  }
  $index[$key] = @($rowIndex)
}

function Parse-CanonicalRowIndex([string]$rowId, [int]$rowCount) {
  $token = Normalize-Token $rowId
  if ($token -notmatch "^canonical_(\d+)$") { return -1 }
  $n = [int]$Matches[1]
  if ($n -lt 1) { return -1 }
  $idx = $n - 1
  if ($idx -ge $rowCount) { return -1 }
  return $idx
}

function Normalize-FieldKey([string]$raw) {
  $token = Normalize-Token $raw
  $token = $token -replace "-", "_"
  $token = $token -replace "\s+", "_"
  $mapped = @{
    "minimum_average" = "min_avg_final"
    "minimum_avg" = "min_avg_final"
    "min_average" = "min_avg_final"
    "competitive_guidance" = "competitive_final"
  }
  if ($mapped.ContainsKey($token)) { return [string]$mapped[$token] }
  return $token
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
  throw "Candidate CSV is empty: $CandidatesPath"
}

$fieldMap = @{
  "min_avg_final" = "Min_Avg_Final"
  "competitive_final" = "Competitive_Final"
  "avg_total" = "Avg_Total"
  "english_req" = "English_Req"
  "english_min" = "English_Min"
  "math_req" = "Math_Req"
  "math_min" = "Math_Min"
  "social_req" = "Social_Req"
  "social_min" = "Social_Min"
  "science_req" = "Science_Req"
  "science_min" = "Science_Min"
  "elective_qty" = "Elective_Qty"
  "elective_pool" = "Elective_Pool"
  "requirement_type" = "Requirement_Type"
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

$profileFilter = Normalize-Confidence $Profile

$fullIndex = @{}
$programIndex = @{}
$identityByRow = @{}
for ($i = 0; $i -lt $canonicalRows.Count; $i++) {
  $row = $canonicalRows[$i]
  $inst = Normalize-Text $row.Institution
  $prog = Normalize-Text $row.Program
  if ((Is-Blank $inst) -or (Is-Blank $prog)) { continue }
  $cred = Normalize-Text $row.Credential_Type
  $url = Normalize-Text $row.Program_URL
  $fullKey = Make-Key -institution $inst -program $prog -credential $cred
  $programKey = Make-Key -institution $inst -program $prog -credential ""
  Add-ToIndex -index $fullIndex -key $fullKey -rowIndex $i
  Add-ToIndex -index $programIndex -key $programKey -rowIndex $i
  $identityByRow[$i] = Make-IdentityKey -institution $inst -program $prog -credential $cred -url $url
}

$overwriteApprovalByRowField = @{}
$overwriteApprovalByIdentityField = @{}
if (Test-Path $IssuePackPath) {
  $issues = @(Import-Csv $IssuePackPath)
  foreach ($issue in $issues) {
    $approval = Normalize-Token $issue.approval_state
    if ($approval -ne "approved_overwrite") { continue }
    $fieldKey = Normalize-FieldKey ([string]$issue.field_name)
    if (Is-Blank $fieldKey) { continue }
    $canonicalRowId = Normalize-Token $issue.canonical_row_id
    if (-not (Is-Blank $canonicalRowId)) {
      $overwriteApprovalByRowField["$canonicalRowId||$fieldKey"] = $true
    }

    $inst = Normalize-Text $issue.institution
    $prog = Normalize-Text $issue.program
    $cred = Normalize-Text $issue.credential
    $url = Normalize-Text $issue.program_url
    if ((-not (Is-Blank $inst)) -and (-not (Is-Blank $prog))) {
      $idKey = Make-IdentityKey -institution $inst -program $prog -credential $cred -url $url
      $overwriteApprovalByIdentityField["$idKey||$fieldKey"] = $true
    }
  }
}

if ($AllowOverwriteExisting) {
  Write-Warning "-AllowOverwriteExisting is legacy. Overwrites still require issue_pack approval_state=approved_overwrite."
}

$changes = @()
$rowsMatched = 0
$rowsNoMatch = 0
$rowsAmbiguous = 0
$rowsMatchedByRowId = 0
$profileSkipped = 0
$errorRowsSkipped = 0
$fieldFillCount = 0
$fieldOverwriteCount = 0
$fieldExistingSkipped = 0
$fieldOverwriteApprovalSkipped = 0
$fieldConfidenceSkipped = 0
$fieldBlankSkipped = 0

foreach ($candidate in $candidates) {
  if (-not (Is-Blank $candidate.error)) {
    $errorRowsSkipped++
    continue
  }

  if (-not (Is-Blank $profileFilter)) {
    $rowProfile = Normalize-Confidence $candidate.profile
    if ($rowProfile -and $rowProfile -ne $profileFilter) {
      $profileSkipped++
      continue
    }
  }

  $targetIndex = -1
  $candidateRowId = Normalize-Text $candidate.index_row_id
  if (-not (Is-Blank $candidateRowId)) {
    $idx = Parse-CanonicalRowIndex -rowId $candidateRowId -rowCount $canonicalRows.Count
    if ($idx -ge 0) {
      $targetIndex = $idx
      $rowsMatchedByRowId++
    }
  }

  if ($targetIndex -lt 0) {
    $inst = Normalize-Text $candidate.institution
    $prog = Normalize-Text $candidate.program_name
    $cred = Normalize-Text $candidate.credential
    if ((Is-Blank $inst) -or (Is-Blank $prog)) {
      $rowsNoMatch++
      continue
    }

    $matches = @()
    if (-not (Is-Blank $cred)) {
      $fullKey = Make-Key -institution $inst -program $prog -credential $cred
      if ($fullIndex.ContainsKey($fullKey)) {
        $matches = @($fullIndex[$fullKey])
      }
    }
    if ($matches.Count -eq 0) {
      $programKey = Make-Key -institution $inst -program $prog -credential ""
      if ($programIndex.ContainsKey($programKey)) {
        $programMatches = @($programIndex[$programKey])
        if ($programMatches.Count -eq 1) {
          $matches = $programMatches
        }
      }
    }
    if ($matches.Count -eq 0) {
      $rowsNoMatch++
      continue
    }
    if ($matches.Count -gt 1) {
      $rowsAmbiguous++
      continue
    }
    $targetIndex = [int]$matches[0]
  }

  $rowsMatched++
  $target = $canonicalRows[$targetIndex]
  $rowIdToken = "canonical_{0:d6}" -f ($targetIndex + 1)
  $identityKey = if ($identityByRow.ContainsKey($targetIndex)) { [string]$identityByRow[$targetIndex] } else { "" }

  foreach ($candidateField in ($fieldMap.Keys | Sort-Object)) {
    $canonicalField = [string]$fieldMap[$candidateField]
    $value = Normalize-Text $candidate.$candidateField
    if (Is-Blank $value) {
      $fieldBlankSkipped++
      continue
    }

    $confidenceField = "{0}_confidence" -f $candidateField
    $confidence = Normalize-Confidence $candidate.$confidenceField
    if (-not ($allowed -contains $confidence)) {
      $fieldConfidenceSkipped++
      continue
    }

    $existing = Normalize-Text $target.$canonicalField
    if (Is-Blank $existing) {
      $target.$canonicalField = $value
      $fieldFillCount++
      $changes += [pscustomobject]@{
        Canonical_Row_ID = $rowIdToken
        Institution = $target.Institution
        Program = $target.Program
        Credential_Type = $target.Credential_Type
        Field = $canonicalField
        Prev_Value = ""
        New_Value = $value
        Mode = "fill"
        Confidence = $confidence
      }
      continue
    }

    if ($existing -eq $value) {
      continue
    }

    $fieldKey = Normalize-FieldKey $candidateField
    $approved = $false
    if ($overwriteApprovalByRowField.ContainsKey("$($rowIdToken.ToLowerInvariant())||$fieldKey")) {
      $approved = $true
    } elseif (-not (Is-Blank $identityKey) -and $overwriteApprovalByIdentityField.ContainsKey("$identityKey||$fieldKey")) {
      $approved = $true
    }

    if (-not $approved) {
      $fieldOverwriteApprovalSkipped++
      continue
    }

    $target.$canonicalField = $value
    $fieldOverwriteCount++
    $changes += [pscustomobject]@{
      Canonical_Row_ID = $rowIdToken
      Institution = $target.Institution
      Program = $target.Program
      Credential_Type = $target.Credential_Type
      Field = $canonicalField
      Prev_Value = $existing
      New_Value = $value
      Mode = "overwrite_approved"
      Confidence = $confidence
    }
  }
}

Write-Host "Canonical source: $canonicalSourcePath"
Write-Host "Candidates loaded: $($candidates.Count)"
Write-Host "Rows matched/no-match/ambiguous: $rowsMatched / $rowsNoMatch / $rowsAmbiguous"
Write-Host "Rows matched by index_row_id: $rowsMatchedByRowId"
Write-Host "Rows skipped: profile=$profileSkipped, errors=$errorRowsSkipped"
Write-Host "Field updates: fill=$fieldFillCount, overwrite=$fieldOverwriteCount, overwrite_approval_skip=$fieldOverwriteApprovalSkipped, confidence_skip=$fieldConfidenceSkipped, blank_skip=$fieldBlankSkipped"
Write-Host "Issue pack used: $IssuePackPath"

if ($changes.Count -gt 0) {
  Write-Host ""
  Write-Host "Changes:"
  $changes | Sort-Object Institution, Program, Field | Format-Table -AutoSize | Out-Host
}

if ($DryRun) {
  Write-Host ""
  Write-Host "Dry run only. No files written."
  return
}

if (($fieldFillCount + $fieldOverwriteCount) -eq 0) {
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

