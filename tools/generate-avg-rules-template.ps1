param(
  [string]$MasterPath = ".\\data\\ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv",
  [string]$FallbackMasterPath = ".\\data\\ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv.new",
  [string]$OutPath = ".\\out\\AvgRules.todo.csv"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Ensure-Dir([string]$path) {
  $dir = Split-Path -Parent $path
  if (-not (Test-Path $dir)) {
    New-Item -ItemType Directory -Path $dir | Out-Null
  }
}

function Is-Blank([object]$v) {
  return ($null -eq $v) -or [string]::IsNullOrWhiteSpace([string]$v)
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
  return $canonicalPath
}

function Try-ParseElectiveQty([string]$s) {
  if (Is-Blank $s) { return $null }
  $t = $s.Trim()
  if ($t -match "^(?i:See Degree|Refer to Degree|Check Notes)$") { return $null }
  if ($t -match "^\d+$") { return [int]$t }
  switch ($t.ToLowerInvariant()) {
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
    default { return $null }
  }
}

function Try-ParseDouble([string]$s) {
  if (Is-Blank $s) { return $null }
  $tmp = 0.0
  if ([double]::TryParse($s.Trim(), [ref]$tmp)) { return $tmp }
  return $null
}

$MasterPath = Resolve-CanonicalPath -canonicalPath $MasterPath -fallbackPath $FallbackMasterPath
if (-not (Test-Path $MasterPath)) {
  throw "Master file not found: $MasterPath. Run .\\tools\\clean-master.ps1 first."
}

$rows = Import-Csv $MasterPath

$needsRules = foreach ($r in $rows) {
  $minAvg = Try-ParseDouble ([string]$r.Min_Avg_Final)
  if ($null -eq $minAvg) { continue }

  $avgTotalExisting = Try-ParseDouble ([string]$r.Avg_Total)
  if ($null -ne $avgTotalExisting -and $avgTotalExisting -gt 0) { continue }

  $qty = Try-ParseElectiveQty ([string]$r.Elective_Qty)
  if ($null -ne $qty) { continue } # already computable as required slots + electives

  [pscustomobject]@{
    Institution       = $r.Institution
    Program           = $r.Program
    Avg_Total         = "" # fill in
    Min_Avg_Final     = $minAvg
    Competitive_Final = $r.Competitive_Final
    Elective_Qty      = $r.Elective_Qty
    Elective_Pool     = $r.Elective_Pool
    English_Req       = $r.English_Req
    Math_Req          = $r.Math_Req
    Social_Req        = $r.Social_Req
    Science_Req       = $r.Science_Req
  }
}

$deduped = $needsRules | Sort-Object Institution, Program -Unique

Ensure-Dir $OutPath
$deduped | Export-Csv -NoTypeInformation -Encoding UTF8 $OutPath
Write-Host "Wrote $($deduped.Count) rows -> $OutPath"
