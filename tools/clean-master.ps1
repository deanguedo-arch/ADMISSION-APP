param(
  [string]$InputPath = ".\\ALBERTA_ADMISSIONS_MASTER_FINAL_v3.csv",
  [string]$OutputPath = ".\\data\\ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv",
  [switch]$DropNaitNonPrograms = $true,
  [switch]$DropMinors = $true,
  [switch]$DropExactDuplicates = $true
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Is-Blank([object]$v) {
  return ($null -eq $v) -or [string]::IsNullOrWhiteSpace([string]$v)
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

if ($DropNaitNonPrograms) {
  $rows = $rows | Where-Object {
    if ($_.Institution -ne "NAIT") { return $true }
    $p = [string]$_.Program
    if ($p -match "^\d+\.\s*") { return $false }
    if ($p -match "government funding for expansion") { return $false }
    if ($p -in @("About", "Accomplishments")) { return $false }
    if ($p -match "^Alumni profile:") { return $false }
    if ($p -match "\bForm\b") { return $false }
    if ($p -match "Before Your Student Applies|After Your Student Applies") { return $false }
    if ($p -match "^All other NAIT programs$") { return $false }
    return $true
  }
}

$canonical = foreach ($r in $rows) {
  $englishReq = if (-not (Is-Blank $r.English_Req)) { $r.English_Req } else { $r.Eng_Req }
  $englishMin = if (-not (Is-Blank $r.English_Min)) { $r.English_Min } else { $r.Eng_Min }

  [pscustomobject]@{
    Institution          = $r.Institution
    Program              = $r.Program
    Credential_Type      = $r.Credential_Type
    Status               = $r.Status

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
