param(
  [string]$VenvPath = ".\\.venv",
  [string]$RequirementsPath = ".\\pipeline\\requirements.txt"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Resolve-PathSafe([string]$p) {
  if ([System.IO.Path]::IsPathRooted($p)) { return $p }
  return (Join-Path (Get-Location) $p)
}

$venv = Resolve-PathSafe $VenvPath
$req = Resolve-PathSafe $RequirementsPath

function Find-PythonExe() {
  $candidates = @(
    (Join-Path $env:LocalAppData "Programs\\Python\\Python312\\python.exe"),
    (Join-Path $env:ProgramFiles "Python312\\python.exe"),
    (Join-Path $env:ProgramFiles "Python311\\python.exe")
  )
  foreach ($c in $candidates) {
    if (Test-Path $c) { return $c }
  }

  $cmd = Get-Command python -ErrorAction SilentlyContinue
  if ($cmd -and (Test-Path $cmd.Source)) {
    if ($cmd.Source -match "\\\\WindowsApps\\\\") { return $null }
    return $cmd.Source
  }
  return $null
}

$pythonExe = Find-PythonExe
if (-not $pythonExe) {
  throw "python not found. Install Python 3.12 (winget id: Python.Python.3.12) and re-run."
}

if (Test-Path $venv) {
  $pyCheck = Join-Path $venv "Scripts\\python.exe"
  if (-not (Test-Path $pyCheck)) {
    Remove-Item -Recurse -Force $venv
  }
}

if (-not (Test-Path $venv)) { & $pythonExe -m venv $venv }

$py = Join-Path $venv "Scripts\\python.exe"
if (-not (Test-Path $py)) {
  throw "Venv python not found: $py"
}

& $py -m pip install --upgrade pip

if (Test-Path $req) {
  & $py -m pip install -r $req
  Write-Host "Installed requirements from $RequirementsPath"
} else {
  Write-Host "No requirements file at $RequirementsPath (skipped)"
}

Write-Host "Venv ready: $VenvPath"
