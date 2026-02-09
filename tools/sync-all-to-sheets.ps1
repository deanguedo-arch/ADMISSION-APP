param(
  [string]$ConfigPath = ".\\config\\sheets_sync.json",
  [switch]$SkipValidation,
  [switch]$SkipPrograms,
  [switch]$SkipElectiveRules,
  [string]$ElectiveRulesCsv = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not $SkipPrograms) {
  Write-Host "Step 1/2: Sync Programs..."
  if ($SkipValidation) {
    & .\\tools\\sync-programs.ps1 -ConfigPath $ConfigPath -SkipValidation | Out-Host
  } else {
    & .\\tools\\sync-programs.ps1 -ConfigPath $ConfigPath | Out-Host
  }
}

if (-not $SkipElectiveRules) {
  Write-Host ""
  Write-Host "Step 2/2: Sync ElectiveRules..."
  if ([string]::IsNullOrWhiteSpace($ElectiveRulesCsv)) {
    & .\\tools\\sync-elective-rules.ps1 -ConfigPath $ConfigPath | Out-Host
  } else {
    & .\\tools\\sync-elective-rules.ps1 -ConfigPath $ConfigPath -CsvPath $ElectiveRulesCsv | Out-Host
  }
}

Write-Host ""
Write-Host "All requested sync steps completed."
