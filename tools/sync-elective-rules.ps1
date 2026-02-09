param(
  [string]$ConfigPath = ".\\config\\sheets_sync.json",
  [string]$CsvPath = "",
  [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-CfgValue([object]$cfg, [string]$name, [object]$defaultValue = $null) {
  $prop = $cfg.PSObject.Properties[$name]
  if ($null -eq $prop) { return $defaultValue }
  if ($null -eq $prop.Value) { return $defaultValue }
  return $prop.Value
}

function Resolve-ElectiveRulesCsv([string]$explicitPath, [string]$sourcePref) {
  if (-not [string]::IsNullOrWhiteSpace($explicitPath)) {
    if (-not (Test-Path $explicitPath)) { throw "ElectiveRules CSV not found: $explicitPath" }
    return $explicitPath
  }

  $pref = [string]$sourcePref
  if ([string]::IsNullOrWhiteSpace($pref)) { $pref = "priority" }
  $pref = $pref.Trim().ToLowerInvariant()

  $paths = @()
  switch ($pref) {
    "prefill" {
      $paths += ".\\out\\ElectiveRules.prefill.csv"
      $paths += ".\\out\\ElectiveRules.priority.csv"
      $paths += ".\\out\\ElectiveRules.todo.csv"
    }
    "todo" {
      $paths += ".\\out\\ElectiveRules.todo.csv"
      $paths += ".\\out\\ElectiveRules.priority.csv"
      $paths += ".\\out\\ElectiveRules.prefill.csv"
    }
    default {
      $paths += ".\\out\\ElectiveRules.priority.csv"
      $paths += ".\\out\\ElectiveRules.prefill.csv"
      $paths += ".\\out\\ElectiveRules.todo.csv"
    }
  }

  foreach ($p in $paths) {
    if (Test-Path $p) { return $p }
  }

  throw "Could not find an ElectiveRules CSV. Expected one of: $($paths -join ', ')"
}

function Validate-ElectiveRulesCsv([string]$path) {
  $rows = Import-Csv $path
  if (-not $rows -or $rows.Count -eq 0) {
    throw "ElectiveRules CSV is empty: $path"
  }

  $header = @($rows[0].PSObject.Properties.Name | ForEach-Object { [string]$_ })
  $headerMap = @{}
  foreach ($h in $header) {
    $headerMap[$h.Trim().ToLowerInvariant()] = $true
  }

  $required = @("institution", "program", "rule_text")
  $missing = @($required | Where-Object { -not $headerMap.ContainsKey($_) })
  if ($missing.Count -gt 0) {
    throw "ElectiveRules CSV missing required columns: $($missing -join ', ')"
  }
}

if (-not (Test-Path $ConfigPath)) {
  throw "Missing config: $ConfigPath. Copy config\\sheets_sync.json.example -> config\\sheets_sync.json and fill values."
}

$cfg = Get-Content $ConfigPath -Raw | ConvertFrom-Json
$webhook = [string](Get-CfgValue $cfg "webhook_url" "")
$token = [string](Get-CfgValue $cfg "sync_token" "")
$sheet = [string](Get-CfgValue $cfg "elective_rules_sheet_name" "ElectiveRules")
$sourcePref = [string](Get-CfgValue $cfg "elective_rules_source" "priority")

if ([string]::IsNullOrWhiteSpace($webhook)) { throw "Config missing webhook_url in $ConfigPath" }
if ([string]::IsNullOrWhiteSpace($token)) { throw "Config missing sync_token in $ConfigPath" }
if ([string]::IsNullOrWhiteSpace($sheet)) { $sheet = "ElectiveRules" }

$resolvedCsvPath = Resolve-ElectiveRulesCsv -explicitPath $CsvPath -sourcePref $sourcePref
Validate-ElectiveRulesCsv -path $resolvedCsvPath

$python = ".\\.venv\\Scripts\\python.exe"
if (-not (Test-Path $python)) {
  throw "Missing venv python at $python. Run: .\\tools\\setup-python.ps1"
}

if ($DryRun) {
  Write-Host "Dry run OK."
  Write-Host "  Config: $ConfigPath"
  Write-Host "  Sheet:  $sheet"
  Write-Host "  CSV:    $resolvedCsvPath"
  return
}

Write-Host "Uploading ElectiveRules from '$resolvedCsvPath' to sheet tab '$sheet'..."
& $python .\\pipeline\\push_to_sheets.py --webhook $webhook --token $token --sheet $sheet --csv $resolvedCsvPath

Write-Host ""
Write-Host "Done."
