param(
  [string]$ManifestPath = "apps_script/appsscript.json",
  [string]$AppsScriptDir = "apps_script",
  [string]$RequiredAccess = "DOMAIN",
  [string]$RequiredTimeZone = "America/Edmonton",
  [string]$RequiredDomainSuffix = "@eips.ca",
  [string[]]$AllowedPublicFunctions = @(
    "doGet",
    "getWebAppBootstrapData",
    "runWebEligibility",
    "doPost",
    "onOpen",
    "onEdit"
  ),
  [switch]$WarnOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$issues = New-Object System.Collections.Generic.List[string]

function Add-Issue([string]$msg) {
  $script:issues.Add($msg)
}

if (-not (Test-Path -LiteralPath $ManifestPath)) {
  throw "Manifest not found: $ManifestPath"
}

$manifestRaw = Get-Content -LiteralPath $ManifestPath -Raw
$manifest = $manifestRaw | ConvertFrom-Json

$actualAccess = [string]($manifest.webapp.access)
if ($actualAccess -ne $RequiredAccess) {
  Add-Issue("Manifest webapp.access expected '$RequiredAccess' but found '$actualAccess'.")
}

$actualTz = [string]($manifest.timeZone)
if ($actualTz -ne $RequiredTimeZone) {
  Add-Issue("Manifest timeZone expected '$RequiredTimeZone' but found '$actualTz'.")
}

if (-not (Test-Path -LiteralPath $AppsScriptDir)) {
  throw "Apps Script directory not found: $AppsScriptDir"
}

$gsFiles = Get-ChildItem -LiteralPath $AppsScriptDir -Filter *.gs -File
if (-not $gsFiles -or $gsFiles.Count -eq 0) {
  throw "No .gs files found in $AppsScriptDir"
}

$allFns = New-Object System.Collections.Generic.List[string]
$combinedCode = ""
$fnRegex = [regex]'(?m)^\s*function\s+([A-Za-z_][A-Za-z0-9_]*)\s*\('

foreach ($file in $gsFiles) {
  $code = Get-Content -LiteralPath $file.FullName -Raw
  $combinedCode += "`n" + $code
  $matches = $fnRegex.Matches($code)
  foreach ($m in $matches) {
    $allFns.Add($m.Groups[1].Value)
  }
}

$publicFns = $allFns |
  Where-Object { -not $_.EndsWith("_") } |
  Sort-Object -Unique

$unexpected = $publicFns |
  Where-Object { $AllowedPublicFunctions -notcontains $_ } |
  Sort-Object -Unique

if ($unexpected -and $unexpected.Count -gt 0) {
  Add-Issue("Unexpected public top-level functions: $($unexpected -join ', ')")
}

$requiredFnSet = @("doGet", "getWebAppBootstrapData", "runWebEligibility")
$missingRequired = $requiredFnSet | Where-Object { $publicFns -notcontains $_ }
if ($missingRequired -and $missingRequired.Count -gt 0) {
  Add-Issue("Missing required public web functions: $($missingRequired -join ', ')")
}

$domainPattern = [regex]::Escape($RequiredDomainSuffix)
if ($combinedCode -notmatch $domainPattern) {
  Add-Issue("Domain suffix '$RequiredDomainSuffix' not found in Apps Script code (expected in domain gate).")
}

if ($issues.Count -gt 0) {
  Write-Host ""
  Write-Host "validate-webapp-surface: FAIL" -ForegroundColor Red
  foreach ($issue in $issues) {
    Write-Host (" - " + $issue) -ForegroundColor Red
  }
  if (-not $WarnOnly) {
    exit 1
  }
  Write-Host ""
  Write-Host "WarnOnly enabled; exiting 0." -ForegroundColor Yellow
  exit 0
}

Write-Host ""
Write-Host "validate-webapp-surface: PASS" -ForegroundColor Green
Write-Host (" - Manifest: " + $ManifestPath)
Write-Host (" - Apps Script files scanned: " + $gsFiles.Count)
Write-Host (" - Public functions: " + ($publicFns -join ", "))
exit 0
