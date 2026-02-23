param(
  [string]$ExpectedRoot = (Join-Path $PSScriptRoot ".."),
  [string]$ExpectedRepo = "deanguedo-arch/ADMISSION-APP"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Normalize-GitHubRemote([string]$url) {
  if ([string]::IsNullOrWhiteSpace($url)) {
    return ""
  }

  $trimmed = $url.Trim()

  $sshMatch = [regex]::Match($trimmed, '^git@github\.com:(.+?)(?:\.git)?$')
  if ($sshMatch.Success) {
    return ("github.com/" + $sshMatch.Groups[1].Value.ToLowerInvariant())
  }

  $httpsMatch = [regex]::Match($trimmed, '^https://github\.com/(.+?)(?:\.git)?/?$')
  if ($httpsMatch.Success) {
    return ("github.com/" + $httpsMatch.Groups[1].Value.ToLowerInvariant())
  }

  return $trimmed.ToLowerInvariant()
}

$expectedRootPath = (Resolve-Path -LiteralPath $ExpectedRoot).Path
$expectedRepoSlug = $ExpectedRepo.Trim().ToLowerInvariant()

$actualRootRaw = (& git rev-parse --show-toplevel 2>$null)
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($actualRootRaw)) {
  Write-Host "FAIL: this folder is not inside a git repo." -ForegroundColor Red
  Write-Host "Run from: $expectedRootPath" -ForegroundColor Yellow
  exit 1
}

$actualRootPath = (Resolve-Path -LiteralPath $actualRootRaw.Trim()).Path
$originRaw = (& git remote get-url origin 2>$null).Trim()
$originNormalized = Normalize-GitHubRemote $originRaw
$branch = (& git rev-parse --abbrev-ref HEAD 2>$null).Trim()

$ok = $true

if ($actualRootPath -ne $expectedRootPath) {
  Write-Host "FAIL: wrong repo root." -ForegroundColor Red
  Write-Host "Expected: $expectedRootPath" -ForegroundColor Yellow
  Write-Host "Actual:   $actualRootPath" -ForegroundColor Yellow
  Write-Host "Fix: cd `"$expectedRootPath`"" -ForegroundColor Cyan
  $ok = $false
}

if (-not $originNormalized.Contains("/$expectedRepoSlug")) {
  Write-Host "FAIL: unexpected origin remote." -ForegroundColor Red
  Write-Host "Expected slug: $expectedRepoSlug" -ForegroundColor Yellow
  Write-Host "Actual origin: $originRaw" -ForegroundColor Yellow
  Write-Host "Fix: git remote set-url origin https://github.com/$expectedRepoSlug.git" -ForegroundColor Cyan
  $ok = $false
}

if (-not $ok) {
  exit 2
}

Write-Host "PASS: workspace is correct." -ForegroundColor Green
Write-Host "Repo root: $actualRootPath"
Write-Host "Branch:    $branch"
Write-Host "Origin:    $originRaw"

if ($branch -eq "main") {
  Write-Host ""
  Write-Host "Note: main is protected. Use feature branch + PR." -ForegroundColor Yellow
}
