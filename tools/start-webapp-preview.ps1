param(
  [int]$Port = 5173,
  [bool]$AutoPort = $true,
  [ValidateSet("auto", "node", "powershell")]
  [string]$Mode = "auto",
  [switch]$OpenBrowser
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

function Test-PortBindable {
  param([int]$Port)

  if ($Port -lt 1 -or $Port -gt 65535) { return $false }

  $listener = $null
  try {
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $Port)
    $listener.Start()
    return $true
  } catch {
    return $false
  } finally {
    if ($listener) {
      try { $listener.Stop() } catch {}
    }
  }
}

function Get-EphemeralAvailablePort {
  $listener = $null
  try {
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
    $listener.Start()
    return ([int]([System.Net.IPEndPoint]$listener.LocalEndpoint).Port)
  } catch {
    return $null
  } finally {
    if ($listener) {
      try { $listener.Stop() } catch {}
    }
  }
}

function Find-AvailablePort {
  param(
    [int]$StartPort,
    [int]$MaxOffset = 2000
  )

  if ($StartPort -lt 1) { $StartPort = 1 }
  if ($StartPort -gt 65535) { return $null }
  $endPort = [Math]::Min(65535, $StartPort + [Math]::Max(0, $MaxOffset))

  for ($candidate = $StartPort; $candidate -le $endPort; $candidate++) {
    $owner = Get-PortOwnerInfo -Port $candidate
    if (-not $owner -and (Test-PortBindable -Port $candidate)) {
      return $candidate
    }
  }

  return $null
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

function Resolve-HtmlIncludes {
  param(
    [Parameter(Mandatory = $true)][string]$Path,
    [Parameter(Mandatory = $true)][string]$Root,
    [string[]]$Stack = @()
  )

  $fullPath = [System.IO.Path]::GetFullPath($Path)
  if (-not $fullPath.StartsWith($Root, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Include path is outside root: $Path"
  }
  if ($Stack -contains $fullPath) {
    throw "Include cycle detected at: $fullPath"
  }
  if (-not (Test-Path -LiteralPath $fullPath -PathType Leaf)) {
    throw "Include file not found: $fullPath"
  }

  $raw = Get-Content -LiteralPath $fullPath -Raw -Encoding UTF8
  $nextStack = @($Stack + $fullPath)
  $rx = [regex]'(?:<!--\s*@include:([A-Za-z0-9_]+)\s*-->)|(?:<\?!=\s*includeHtml_\(\s*["'']([A-Za-z0-9_]+)["'']\s*\)\s*;?\s*\?>)'
  return $rx.Replace($raw, {
    param($m)
    $name = if ($m.Groups[1].Success) {
      [string]$m.Groups[1].Value
    } else {
      [string]$m.Groups[2].Value
    }
    $includePath = Join-Path $Root ($name + ".html")
    return Resolve-HtmlIncludes -Path $includePath -Root $Root -Stack $nextStack
  })
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
  if ($OpenBrowser) {
    try {
      Start-Process ("http://localhost:{0}/WebApp.html?mock=1" -f $Port) | Out-Null
    } catch {}
  }

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

        $ext = [System.IO.Path]::GetExtension($fullPath).ToLowerInvariant()
        if ($ext -eq ".html") {
          $html = Resolve-HtmlIncludes -Path $fullPath -Root $rootFull
          $bytes = [System.Text.Encoding]::UTF8.GetBytes($html)
        } else {
          $bytes = [System.IO.File]::ReadAllBytes($fullPath)
        }
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

function Resolve-NodeExecutable {
  $cmd = Get-Command node -ErrorAction SilentlyContinue
  if ($cmd -and $cmd.Source) {
    return [string]$cmd.Source
  }

  $candidates = @()
  if ($env:ProgramFiles) {
    $candidates += (Join-Path $env:ProgramFiles "nodejs\node.exe")
  }
  if (${env:ProgramFiles(x86)}) {
    $candidates += (Join-Path ${env:ProgramFiles(x86)} "nodejs\node.exe")
  }
  if ($env:LOCALAPPDATA) {
    $candidates += (Join-Path $env:LOCALAPPDATA "Programs\nodejs\node.exe")
  }
  if ($env:NVM_SYMLINK) {
    $candidates += (Join-Path $env:NVM_SYMLINK "node.exe")
  }

  foreach ($candidate in $candidates) {
    if (-not $candidate) { continue }
    if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) { continue }
    try {
      return (Resolve-Path -LiteralPath $candidate).Path
    } catch {
      return $candidate
    }
  }

  return $null
}

$nodeExe = Resolve-NodeExecutable
$useNode = $false
switch ($Mode.ToLowerInvariant()) {
  "node" {
    if (-not $nodeExe) {
      throw "Mode=node requested but Node.js is not installed or not in PATH."
    }
    $useNode = $true
  }
  "powershell" {
    $useNode = $false
  }
  default {
    $useNode = [bool]$nodeExe
  }
}

$requestedPort = $Port
$portOwner = Get-PortOwnerInfo -Port $Port
if ($portOwner) {
  $ownerLabel = if ($portOwner.Name) { "$($portOwner.Name) (PID $($portOwner.Pid))" } else { "PID $($portOwner.Pid)" }
  $suggestedPort = Find-AvailablePort -StartPort ($Port + 1)
  if (-not $suggestedPort -and $AutoPort) {
    $suggestedPort = Get-EphemeralAvailablePort
  }

  if ($AutoPort -and $suggestedPort -and ($suggestedPort -ne $Port)) {
    Write-Host ("Port {0} is in use by {1}. Auto-selecting free port {2}." -f $Port, $ownerLabel, $suggestedPort) -ForegroundColor Yellow
    $Port = $suggestedPort
  } else {
    $hintPort = if ($suggestedPort) { $suggestedPort } else { $Port + 1 }
    $extraHint = if ($AutoPort) { "No free replacement port was found automatically." } else { "Auto-port selection is disabled (use -AutoPort `$true to enable it)." }
    throw "Port $Port is already in use by $ownerLabel. $extraHint Stop that process or run with a different port (for example: -Port $hintPort)."
  }
}

if ($useNode) {
  if (-not (Test-Path -LiteralPath $nodeServerScript)) {
    throw "Node server script not found at $nodeServerScript"
  }
  Write-Host "Starting local web app preview (Node static server)..." -ForegroundColor Cyan
  Write-Host ("URL: http://localhost:{0}/WebApp.html?mock=1" -f $Port) -ForegroundColor Green
  Write-Host "Press Ctrl+C to stop." -ForegroundColor DarkGray
  if ($OpenBrowser) {
    try {
      Start-Process ("http://localhost:{0}/WebApp.html?mock=1" -f $Port) | Out-Null
    } catch {}
  }
  Set-Location $repoRoot
  & $nodeExe $nodeServerScript --port $Port --root "apps_script"
  return
}

if ($Mode -eq "auto" -and -not $nodeExe) {
  Write-Host "Node.js not found. Falling back to PowerShell static server." -ForegroundColor Yellow
}
Start-PowerShellStaticServer -Root $webRoot -Port $Port
