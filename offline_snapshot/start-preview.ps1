param(
  [int]$Port = 5180,
  [ValidateSet("auto", "node", "python")]
  [string]$Mode = "auto",
  [switch]$OpenBrowser
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$snapshotRoot = $PSScriptRoot
$repoRoot = (Resolve-Path (Join-Path $snapshotRoot "..")).Path
$siteRoot = (Resolve-Path (Join-Path $snapshotRoot "site")).Path
$indexPath = Join-Path $siteRoot "index.html"
$nodeServerScript = Join-Path $repoRoot "tools\local-preview-server.js"

if (-not (Test-Path -LiteralPath $indexPath -PathType Leaf)) {
  throw "Offline snapshot site not found at $indexPath. Build first with .\BUILD_OFFLINE_SNAPSHOT.bat"
}

function Resolve-NodeExe {
  $cmd = Get-Command node -ErrorAction SilentlyContinue
  if ($cmd -and $cmd.Source) { return [string]$cmd.Source }

  $bundled = Join-Path $repoRoot "nodeforadmissionsscraper\node.exe"
  if (Test-Path -LiteralPath $bundled -PathType Leaf) {
    return (Resolve-Path -LiteralPath $bundled).Path
  }
  return $null
}

function Resolve-PythonExe {
  $venv = Join-Path $repoRoot ".venv\Scripts\python.exe"
  if (Test-Path -LiteralPath $venv -PathType Leaf) {
    return (Resolve-Path -LiteralPath $venv).Path
  }
  $cmd = Get-Command python -ErrorAction SilentlyContinue
  if ($cmd -and $cmd.Source) { return [string]$cmd.Source }
  return $null
}

$nodeExe = Resolve-NodeExe
$pythonExe = Resolve-PythonExe

$useNode = $false
switch ($Mode.ToLowerInvariant()) {
  "node" {
    if (-not $nodeExe) { throw "Mode=node requested but Node.js was not found." }
    $useNode = $true
  }
  "python" {
    if (-not $pythonExe) { throw "Mode=python requested but Python was not found." }
    $useNode = $false
  }
  default {
    $useNode = [bool]$nodeExe
    if (-not $useNode -and -not $pythonExe) {
      throw "No runtime found. Install Node.js or Python to run local preview."
    }
  }
}

$url = "http://localhost:$Port/index.html"

if ($useNode) {
  if (-not (Test-Path -LiteralPath $nodeServerScript -PathType Leaf)) {
    throw "Node static server script not found: $nodeServerScript"
  }
  Write-Host "Starting offline snapshot preview (Node static server)..." -ForegroundColor Cyan
  Write-Host "URL: $url" -ForegroundColor Green
  Write-Host "Press Ctrl+C to stop." -ForegroundColor DarkGray
  if ($OpenBrowser) {
    try { Start-Process $url | Out-Null } catch {}
  }
  Set-Location $repoRoot
  & $nodeExe $nodeServerScript --port $Port --root "offline_snapshot/site"
  exit $LASTEXITCODE
}

Write-Host "Starting offline snapshot preview (Python http.server)..." -ForegroundColor Cyan
Write-Host "URL: $url" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop." -ForegroundColor DarkGray
if ($OpenBrowser) {
  try { Start-Process $url | Out-Null } catch {}
}

Set-Location $repoRoot
& $pythonExe -m http.server $Port --directory $siteRoot
exit $LASTEXITCODE
