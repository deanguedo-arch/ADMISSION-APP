param(
  [int]$Port = 5173,
  [ValidateSet("auto", "node", "powershell")]
  [string]$Mode = "auto"
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$webRoot = Join-Path $repoRoot "apps_script"
$nodeServerScript = Join-Path $repoRoot "tools\local-preview-server.js"

if (-not (Test-Path -LiteralPath $webRoot)) {
  throw "apps_script folder not found at $webRoot"
}

function Get-PortOwnerInfo {
  param([int]$Port)

  try {
    $listeners = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction Stop
  } catch {
    return $null
  }

  if (-not $listeners) { return $null }
  $ownerPid = ($listeners | Select-Object -First 1).OwningProcess
  $ownerName = ""
  try {
    $proc = Get-Process -Id $ownerPid -ErrorAction Stop
    $ownerName = [string]$proc.ProcessName
  } catch {}

  return @{
    Port = $Port
    Pid = $ownerPid
    Name = $ownerName
  }
}

function Get-ContentTypeForPath {
  param([string]$Path)
  $ext = [System.IO.Path]::GetExtension($Path).ToLowerInvariant()
  switch ($ext) {
    ".html" { return "text/html; charset=utf-8" }
    ".js" { return "application/javascript; charset=utf-8" }
    ".css" { return "text/css; charset=utf-8" }
    ".json" { return "application/json; charset=utf-8" }
    ".svg" { return "image/svg+xml" }
    ".png" { return "image/png" }
    ".jpg" { return "image/jpeg" }
    ".jpeg" { return "image/jpeg" }
    ".ico" { return "image/x-icon" }
    default { return "application/octet-stream" }
  }
}

function Write-StaticResponse {
  param(
    [Parameter(Mandatory = $true)]$Context,
    [Parameter(Mandatory = $true)][int]$StatusCode,
    [Parameter(Mandatory = $true)][string]$Body
  )
  $response = $Context.Response
  $bytes = [System.Text.Encoding]::UTF8.GetBytes($Body)
  $response.StatusCode = $StatusCode
  $response.ContentType = "text/plain; charset=utf-8"
  $response.ContentLength64 = $bytes.Length
  $response.AddHeader("Cache-Control", "no-store")
  $response.OutputStream.Write($bytes, 0, $bytes.Length)
}

function Start-PowerShellStaticServer {
  param(
    [Parameter(Mandatory = $true)][string]$Root,
    [Parameter(Mandatory = $true)][int]$Port
  )

  $rootFull = [System.IO.Path]::GetFullPath($Root)
  if (-not $rootFull.EndsWith([System.IO.Path]::DirectorySeparatorChar)) {
    $rootFull = $rootFull + [System.IO.Path]::DirectorySeparatorChar
  }

  $listener = New-Object System.Net.HttpListener
  $prefix = "http://localhost:$Port/"
  $listener.Prefixes.Add($prefix)
  $listener.Start()

  Write-Host "Starting local web app preview (PowerShell static server)..." -ForegroundColor Cyan
  Write-Host ("URL: http://localhost:{0}/WebApp.html?mock=1" -f $Port) -ForegroundColor Green
  Write-Host "Press Ctrl+C to stop." -ForegroundColor DarkGray

  try {
    while ($listener.IsListening) {
      $context = $listener.GetContext()
      try {
        $requestPath = [string]($context.Request.Url.AbsolutePath)
        if ([string]::IsNullOrWhiteSpace($requestPath) -or $requestPath -eq "/") {
          $requestPath = "/WebApp.html"
        }

        $relativePath = [System.Uri]::UnescapeDataString($requestPath.TrimStart("/"))
        if ([string]::IsNullOrWhiteSpace($relativePath)) {
          $relativePath = "WebApp.html"
        }

        $candidate = Join-Path $rootFull $relativePath
        $fullPath = [System.IO.Path]::GetFullPath($candidate)

        if (-not $fullPath.StartsWith($rootFull, [System.StringComparison]::OrdinalIgnoreCase)) {
          Write-StaticResponse -Context $context -StatusCode 403 -Body "Forbidden"
          continue
        }

        if (Test-Path -LiteralPath $fullPath -PathType Container) {
          $fullPath = Join-Path $fullPath "WebApp.html"
        }

        if (-not (Test-Path -LiteralPath $fullPath -PathType Leaf)) {
          Write-StaticResponse -Context $context -StatusCode 404 -Body "Not found"
          continue
        }

        $bytes = [System.IO.File]::ReadAllBytes($fullPath)
        $response = $context.Response
        $response.StatusCode = 200
        $response.ContentType = Get-ContentTypeForPath -Path $fullPath
        $response.ContentLength64 = $bytes.Length
        $response.AddHeader("Cache-Control", "no-store")
        $response.OutputStream.Write($bytes, 0, $bytes.Length)
      } catch {
        try {
          Write-StaticResponse -Context $context -StatusCode 500 -Body "Server error"
        } catch {}
      } finally {
        try {
          $context.Response.OutputStream.Close()
        } catch {}
      }
    }
  } finally {
    try {
      $listener.Stop()
      $listener.Close()
    } catch {}
  }
}

$nodeCmd = Get-Command node -ErrorAction SilentlyContinue
$useNode = $false
switch ($Mode.ToLowerInvariant()) {
  "node" {
    if (-not $nodeCmd) {
      throw "Mode=node requested but Node.js is not installed or not in PATH."
    }
    $useNode = $true
  }
  "powershell" {
    $useNode = $false
  }
  default {
    $useNode = [bool]$nodeCmd
  }
}

 $portOwner = Get-PortOwnerInfo -Port $Port
 if ($portOwner) {
  $ownerLabel = if ($portOwner.Name) { "$($portOwner.Name) (PID $($portOwner.Pid))" } else { "PID $($portOwner.Pid)" }
  throw "Port $Port is already in use by $ownerLabel. Stop that process or run with a different port (for example: -Port 5200)."
}

if ($useNode) {
  if (-not (Test-Path -LiteralPath $nodeServerScript)) {
    throw "Node server script not found at $nodeServerScript"
  }
  Write-Host "Starting local web app preview (Node static server)..." -ForegroundColor Cyan
  Write-Host ("URL: http://localhost:{0}/WebApp.html?mock=1" -f $Port) -ForegroundColor Green
  Write-Host "Press Ctrl+C to stop." -ForegroundColor DarkGray
  Set-Location $repoRoot
  & node $nodeServerScript --port $Port --root "apps_script"
  return
}

if ($Mode -eq "auto" -and -not $nodeCmd) {
  Write-Host "Node.js not found. Falling back to PowerShell static server." -ForegroundColor Yellow
}
Start-PowerShellStaticServer -Root $webRoot -Port $Port
