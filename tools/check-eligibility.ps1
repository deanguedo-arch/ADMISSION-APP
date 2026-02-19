param(
  [string]$MasterPath = ".\\data\\ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv",
  [string]$FallbackMasterPath = ".\\data\\ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv.new",
  [string]$StudentPath = "",
  [double]$AdmissionAverage = [double]::NaN,
  [string]$Institution = "",
  [switch]$IncludeSuspended = $false,
  [string]$OutPath = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Is-Blank([object]$v) {
  return ($null -eq $v) -or [string]::IsNullOrWhiteSpace([string]$v)
}

function Try-ParseDouble([string]$s) {
  if (Is-Blank $s) { return $null }
  $tmp = 0.0
  if ([double]::TryParse($s, [ref]$tmp)) { return $tmp }
  return $null
}

function Norm([string]$s) {
  if ($null -eq $s) { return "" }
  $t = ($s -replace "[\u2010-\u2015]", "-").Trim()
  $t = ($t -replace "\s+", " ")
  return $t
}

function CanonCourseKey([string]$s) {
  $t = (Norm $s).ToUpperInvariant()
  $t = $t -replace "\.", ""
  $t = $t -replace "\s+", " "
  return $t
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

function Build-CourseMapFromStudentFile([string]$path) {
  if (-not (Test-Path $path)) { throw "Student file not found: $path" }
  if ($path.ToLowerInvariant().EndsWith(".csv")) {
    $rows = Import-Csv $path
    $map = @{}
    foreach ($r in $rows) {
      $course = Norm $r.Course
      if (Is-Blank $course) { continue }
      $mark = Try-ParseDouble ([string]$r.Mark)
      if ($null -eq $mark) { continue }
      $map[(CanonCourseKey $course)] = $mark
    }
    return $map
  }

  if ($path.ToLowerInvariant().EndsWith(".json")) {
    $obj = Get-Content $path -Raw | ConvertFrom-Json
    $map = @{}
    foreach ($k in $obj.courses.psobject.Properties.Name) {
      $map[(CanonCourseKey $k)] = [double]$obj.courses.$k
    }
    return $map
  }

  throw "Unsupported student file format (use .csv or .json): $path"
}

function Resolve-ScienceFromFlags($row) {
  $req = @()
  foreach ($pair in @(
    @{Flag="Bio_30_Req"; Course="Biology 30"},
    @{Flag="Chem_30_Req"; Course="Chemistry 30"},
    @{Flag="Phys_30_Req"; Course="Physics 30"},
    @{Flag="Sci_30_Req"; Course="Science 30"}
  )) {
    $val = Norm ([string]$row.($pair.Flag))
    if ($val.ToLowerInvariant() -eq "yes") { $req += $pair.Course }
  }
  return $req
}

function Parse-Req([string]$subject, [string]$reqText) {
  $t = Norm $reqText
  if (Is-Blank $t) { return @{ kind="none" } }
  if ($t -match "^(See Degree|Refer to Degree)$") { return @{ kind="unknown"; reason=$t } }
  if ($t -match "(placement|assessment|test)") { return @{ kind="assessment"; raw=$t } }

  $prefix =
    if ($subject -eq "english") { "English " }
    elseif ($subject -eq "math") { "Math " }
    elseif ($subject -eq "social") { "Social Studies " }
    else { "" }

  # Split on " or " (case-insensitive) for alternatives.
  $parts = $t -split "\s+(?i:or)\s+"
  $alts = @()
  foreach ($p in $parts) {
    $q = (Norm $p) -replace "^(?i:English|Math|Social Studies|Social)\s+", ""
    if ($q -match "^\d{2}-\d$") {
      $alts += ($prefix + $q)
    } else {
      # Science strings like "Bio 30, Chem 30" handled elsewhere; here keep as-is.
      $alts += (Norm $p)
    }
  }
  return @{ kind="courses"; courses=$alts }
}

function Science-Alts([string]$reqText, [string[]]$flagCourses) {
  $fc = @(@($flagCourses) | Where-Object { -not (Is-Blank $_) })
  if ($fc.Count -gt 0) { return @{ kind="courses"; courses=$fc } }
  $t = Norm $reqText
  if (Is-Blank $t) { return @{ kind="none" } }
  if ($t -match "^(See Degree|Refer to Degree)$") { return @{ kind="unknown"; reason=$t } }
  $parts = $t -split "\s*,\s*"
  $courses = @()
  foreach ($p in $parts) {
    $q = Norm $p
    if (Is-Blank $q) { continue }
    switch -Regex ($q) {
      "^(?i:Bio)\s*30$" { $courses += "Biology 30"; continue }
      "^(?i:Chem)\s*30$" { $courses += "Chemistry 30"; continue }
      "^(?i:Phys)\s*30$" { $courses += "Physics 30"; continue }
      "^(?i:Sci)\s*30$" { $courses += "Science 30"; continue }
      default { $courses += $q; continue }
    }
  }
  return @{ kind="courses"; courses=$courses }
}

function Check-CourseRequirement($courseMap, [string[]]$courses, [double]$minMark, [string]$label) {
  $best = $null
  $bestCourse = $null

  foreach ($c in $courses) {
    $k = CanonCourseKey $c
    if ($courseMap.ContainsKey($k)) {
      $m = [double]$courseMap[$k]
      if (($null -eq $best) -or ($m -gt $best)) {
        $best = $m
        $bestCourse = $c
      }
    }
  }

  if ($null -eq $best) {
    return @{ ok=$false; reason="Missing $label ($($courses -join ' OR '))"; detail="" }
  }
  if ($best -lt $minMark) {
    return @{ ok=$false; reason="$label mark too low"; detail="$bestCourse=$best < $minMark" }
  }
  return @{ ok=$true; reason=""; detail="$bestCourse=$best" }
}

$MasterPath = Resolve-CanonicalPath -canonicalPath $MasterPath -fallbackPath $FallbackMasterPath
if (-not (Test-Path $MasterPath)) {
  throw "Master file not found: $MasterPath. Run .\\tools\\clean-master.ps1 first."
}

$programs = Import-Csv $MasterPath

if (-not (Is-Blank $Institution)) {
  $programs = $programs | Where-Object { $_.Institution -eq $Institution }
}
if (-not $IncludeSuspended) {
  $programs = $programs | Where-Object { $_.Status -ne "Suspended" }
}

$courseMap = @{}
if (-not (Is-Blank $StudentPath)) {
  $courseMap = Build-CourseMapFromStudentFile $StudentPath
}

if ($courseMap.Count -eq 0) {
  Write-Host "No student course file provided (or it was empty)."
  Write-Host "Provide -StudentPath student.csv or student.json"
  exit 2
}

$results = foreach ($p in $programs) {
  $reasons = @()
  $unknowns = @()
  $advisories = @()
  $flags = @()

  $minAvg = Try-ParseDouble ([string]$p.Min_Avg_Final)
  if ($null -ne $minAvg -and -not [double]::IsNaN($AdmissionAverage)) {
    if ($AdmissionAverage -lt $minAvg) { $reasons += "Admission average too low ($AdmissionAverage < $minAvg)" }
  }

  $competitive = Norm ([string]$p.Competitive_Final)
  if (-not (Is-Blank $competitive) -and $competitive -notmatch "^(?i:Minimum Only|See Degree|Refer to Degree)$") {
    $flags += "Competitive"
  }

  $engMin = (Try-ParseDouble ([string]$p.English_Min))
  if ($null -eq $engMin) { $engMin = 0.0 }
  $mathMin = (Try-ParseDouble ([string]$p.Math_Min))
  if ($null -eq $mathMin) { $mathMin = 0.0 }
  $socMin = (Try-ParseDouble ([string]$p.Social_Min))
  if ($null -eq $socMin) { $socMin = 0.0 }
  $sciMin = (Try-ParseDouble ([string]$p.Science_Min))
  if ($null -eq $sciMin) { $sciMin = 0.0 }

  $eng = Parse-Req "english" ([string]$p.English_Req)
  if ($eng.kind -eq "unknown") { $unknowns += "English: $($eng.reason)" }
  elseif ($eng.kind -eq "assessment") { $flags += "Assessment"; $advisories += "English: assessment/placement required" }
  elseif ($eng.kind -eq "courses" -and $eng.courses.Count -gt 0 -and $engMin -gt 0) {
    $chk = Check-CourseRequirement $courseMap $eng.courses $engMin "English"
    if (-not $chk.ok) { $reasons += ($chk.reason + ($(if($chk.detail){": $($chk.detail)"}else{""}))) }
  }

  $math = Parse-Req "math" ([string]$p.Math_Req)
  if ($math.kind -eq "unknown") { $unknowns += "Math: $($math.reason)" }
  elseif ($math.kind -eq "assessment") { $flags += "Assessment"; $advisories += "Math: assessment/placement required" }
  elseif ($math.kind -eq "courses" -and $math.courses.Count -gt 0 -and $mathMin -gt 0) {
    $chk = Check-CourseRequirement $courseMap $math.courses $mathMin "Math"
    if (-not $chk.ok) { $reasons += ($chk.reason + ($(if($chk.detail){": $($chk.detail)"}else{""}))) }
  }

  $soc = Parse-Req "social" ([string]$p.Social_Req)
  if ($soc.kind -eq "unknown") { $unknowns += "Social: $($soc.reason)" }
  elseif ($soc.kind -eq "courses" -and $soc.courses.Count -gt 0 -and $socMin -gt 0) {
    $chk = Check-CourseRequirement $courseMap $soc.courses $socMin "Social Studies"
    if (-not $chk.ok) { $reasons += ($chk.reason + ($(if($chk.detail){": $($chk.detail)"}else{""}))) }
  }

  $flagSci = Resolve-ScienceFromFlags $p
  $sci = Science-Alts ([string]$p.Science_Req) $flagSci
  if ($sci.kind -eq "unknown") { $unknowns += "Science: $($sci.reason)" }
  elseif ($sci.kind -eq "courses" -and $sci.courses.Count -gt 0 -and $sciMin -gt 0) {
    $chk = Check-CourseRequirement $courseMap $sci.courses $sciMin "Science"
    if (-not $chk.ok) { $reasons += ($chk.reason + ($(if($chk.detail){": $($chk.detail)"}else{""}))) }
  }

  $electiveInfo = Norm ([string]$p.Elective_Qty)
  if (-not (Is-Blank $electiveInfo) -and $electiveInfo -notmatch "^(0|None)$") {
    $unknowns += "Electives not evaluated ($electiveInfo)"
  }

  $eligible = ($reasons.Count -eq 0)
  $checkable = ($unknowns.Count -eq 0)

  [pscustomobject]@{
    Institution = $p.Institution
    Program = $p.Program
    Credential_Type = $p.Credential_Type
    Status = $p.Status
    Eligible = $eligible
    Checkable = $checkable
    Flags = (($flags | Sort-Object -Unique) -join ", ")
    Competitive_Guidance = $competitive
    Reasons = ($reasons -join " | ")
    Notes = ((@($unknowns + $advisories) | Where-Object { -not (Is-Blank $_) }) -join " | ")
  }
}

$sorted = $results | Sort-Object `
  @{ Expression = "Eligible"; Descending = $true }, `
  @{ Expression = "Checkable"; Descending = $true }, `
  "Institution", "Program"

if (-not (Is-Blank $OutPath)) {
  $sorted | Export-Csv -NoTypeInformation -Encoding UTF8 $OutPath
  Write-Host "Wrote results -> $OutPath"
} else {
  $sorted | Select-Object -First 50 | Format-Table -AutoSize
  Write-Host ""
  Write-Host "Tip: add -OutPath .\\out\\results.csv to export all results"
}
