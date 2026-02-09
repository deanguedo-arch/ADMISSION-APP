param(
  [string]$MasterPath = ".\\data\\ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv",
  [string]$FallbackMasterPath = ".\\data\\ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv.new",
  [string]$OutPath = ".\\out\\ElectiveRules.todo.csv"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

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

function Is-Blank([object]$v) {
  return ($null -eq $v) -or [string]::IsNullOrWhiteSpace([string]$v)
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

function Has-ElectiveRuleText([string]$text) {
  if (Is-Blank $text) { return $false }
  $t = $text.ToLowerInvariant()
  if ($t -match "\b(max|maximum|at most|up to)\b") { return $true }
  if ($t -match "admission subjects?\s+must\s+be\s+from\s+groups?") { return $true }
  if ($t -match "(additional|more).+from\s+groups?") { return $true }
  if ($t -match "each\s+subject\s+must\s+be") { return $true }
  return $false
}

$csvPath = Resolve-CanonicalPath -canonicalPath $MasterPath -fallbackPath $FallbackMasterPath
$rows = Import-Csv $csvPath

$todo = foreach ($r in $rows) {
  if ([string]$r.Status -ne "Active") { continue }

  $qty = Try-ParseElectiveQty ([string]$r.Elective_Qty)
  if ($null -eq $qty -or $qty -le 0) { continue }

  $pool = [string]$r.Elective_Pool
  if (Is-Blank $pool) { continue }

  $ruleText = [string]$r.Requirement_Type
  if (Has-ElectiveRuleText $ruleText) { continue }

  [pscustomobject]@{
    Institution     = $r.Institution
    Program         = $r.Program
    Credential_Type = $r.Credential_Type
    Elective_Qty    = $r.Elective_Qty
    Elective_Pool   = $r.Elective_Pool
    Requirement_Type = $r.Requirement_Type
    Rule_Text       = "" # fill this when a cap/constraint exists on source site
  }
}

$deduped = $todo | Sort-Object Institution, Program, Credential_Type -Unique
Ensure-Dir $OutPath
$deduped | Export-Csv -NoTypeInformation -Encoding UTF8 $OutPath
Write-Host "Wrote $($deduped.Count) rows -> $OutPath"
