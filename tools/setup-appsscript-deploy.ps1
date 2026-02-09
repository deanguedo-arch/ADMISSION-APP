param(
  [string]$ScriptId = "",
  [string]$DeploymentId = "",
  [switch]$SkipInstall
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Command-Exists([string]$name) {
  try {
    Get-Command $name -ErrorAction Stop | Out-Null
    return $true
  } catch {
    return $false
  }
}

function Require-Tool([string]$name, [string]$wingetId) {
  if (Command-Exists $name) { return }
  if ($SkipInstall) {
    throw "Missing tool '$name'. Install it and re-run."
  }
  Write-Host "Installing $name via winget ($wingetId)..."
  winget install --id $wingetId --silent --accept-source-agreements --accept-package-agreements
  if (-not (Command-Exists $name)) {
    throw "Could not find '$name' after install. Restart shell and re-run."
  }
}

function Gh-IsAuthed() {
  try {
    gh auth status | Out-Null
    return $true
  } catch {
    return $false
  }
}

Write-Host "Checking required tools..."
Require-Tool -name "node" -wingetId "OpenJS.NodeJS.LTS"
Require-Tool -name "npm" -wingetId "OpenJS.NodeJS.LTS"
Require-Tool -name "gh" -wingetId "GitHub.cli"

if (-not (Command-Exists "clasp")) {
  Write-Host "Installing clasp globally..."
  npm install --global @google/clasp
}

$claspRcPath = Join-Path $env:USERPROFILE ".clasprc.json"
if (-not (Test-Path $claspRcPath)) {
  Write-Host ""
  Write-Host "No ~/.clasprc.json found. Running 'clasp login' (interactive browser sign-in)..."
  clasp login
}

if (-not (Test-Path $claspRcPath)) {
  throw "clasp auth file still missing at $claspRcPath"
}

if (-not (Gh-IsAuthed)) {
  Write-Host ""
  Write-Host "GitHub CLI is not authenticated."
  Write-Host "Run: gh auth login"
  Write-Host "Then re-run this script to auto-set repo secrets."
  exit 0
}

Write-Host ""
Write-Host "Setting GitHub secret: CLASPRC_JSON"
$claspJsonRaw = Get-Content -LiteralPath $claspRcPath -Raw
$claspJsonRaw | gh secret set CLASPRC_JSON

if (-not [string]::IsNullOrWhiteSpace($ScriptId)) {
  Write-Host "Setting GitHub secret: APPS_SCRIPT_ID"
  gh secret set APPS_SCRIPT_ID --body "$ScriptId" | Out-Null
}

if (-not [string]::IsNullOrWhiteSpace($DeploymentId)) {
  Write-Host "Setting GitHub secret: APPS_SCRIPT_DEPLOYMENT_ID"
  gh secret set APPS_SCRIPT_DEPLOYMENT_ID --body "$DeploymentId" | Out-Null
}

Write-Host ""
Write-Host "Done."
Write-Host "If APPS_SCRIPT_ID / APPS_SCRIPT_DEPLOYMENT_ID were not provided, set them manually in GitHub Secrets."
