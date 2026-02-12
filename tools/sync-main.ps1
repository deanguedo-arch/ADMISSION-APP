param(
  [string]$Remote = "origin",
  [string]$Branch = "main",
  [switch]$SkipPush
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Invoke-GitChecked {
  param([string[]]$CmdArgs)
  & git @CmdArgs
  if ($LASTEXITCODE -ne 0) {
    throw "git $($CmdArgs -join ' ') failed with exit code $LASTEXITCODE"
  }
}

$stashTag = "autosync-{0}" -f (Get-Date -Format "yyyyMMdd-HHmmss")
$stashed = $false

Write-Host "== Sync main helper =="
Write-Host "Remote: $Remote  Branch: $Branch"

$dirty = (& git status --porcelain)
if ($LASTEXITCODE -ne 0) {
  throw "Unable to read git status."
}

if ($dirty) {
  Write-Host "Working tree has local changes. Stashing first..."
  Invoke-GitChecked -CmdArgs @("stash", "push", "-u", "-m", $stashTag)
  $stashed = $true
}

try {
  Invoke-GitChecked -CmdArgs @("fetch", $Remote)
  Invoke-GitChecked -CmdArgs @("pull", "--rebase", $Remote, $Branch)

  if (-not $SkipPush) {
    Invoke-GitChecked -CmdArgs @("push", $Remote, $Branch)
  } else {
    Write-Host "SkipPush set: not pushing."
  }
}
finally {
  if ($stashed) {
    $stashList = (& git stash list)
    if ($LASTEXITCODE -ne 0) {
      throw "Unable to read stash list."
    }

    if ($stashList -match [regex]::Escape($stashTag)) {
      Write-Host "Restoring stashed changes..."
      & git stash pop
      if ($LASTEXITCODE -ne 0) {
        throw "stash pop had conflicts. Resolve manually, then continue."
      }
    }
  }
}

Write-Host "Sync complete."
