param(
  [string]$CsvPath = ".\\data\\ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv",
  [string]$BaselinePath = ".\\out\\last_good_programs.csv",
  [int]$MinRows = 100,
  [double]$MaxRowDropPercent = 35,
  [string[]]$RequiredInstitutions = @("NAIT", "NorQuest", "MacEwan")
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

if (Test-Path $BaselinePath) {
  $baselineRows = Import-Csv $BaselinePath
  if ($baselineRows -and $baselineRows.Count -gt 0) {
    $baselineCount = [double]$baselineRows.Count
    $dropPercent = ((($baselineCount - [double]$rowCount) / $baselineCount) * 100)
    if ($dropPercent -gt $MaxRowDropPercent) {
      throw "Validation failed: row count dropped by $([math]::Round($dropPercent,2))% (baseline=$baselineCount, current=$rowCount, max=$MaxRowDropPercent%)"
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
