param(
    [string]$Message = "",
    [switch]$NoPush
)

$ErrorActionPreference = "Stop"

function Assert-GitRepo {
    $inside = (git rev-parse --is-inside-work-tree 2>$null)
    if ($LASTEXITCODE -ne 0 -or $inside.Trim() -ne "true") {
        throw "Current directory is not a git repository."
    }
}

function Assert-OriginRemote {
    $origin = (git remote get-url origin 2>$null)
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($origin)) {
        throw "Remote 'origin' is not configured. Use: git remote add origin <repo-url>"
    }
}

Assert-GitRepo
Assert-OriginRemote

if ([string]::IsNullOrWhiteSpace($Message)) {
    $Message = "chore: sync $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
}

git add -A

$staged = (git diff --cached --name-only)
if ([string]::IsNullOrWhiteSpace($staged)) {
    Write-Host "No staged changes. Nothing to commit."
    exit 0
}

git commit -m $Message

if ($NoPush) {
    Write-Host "Committed locally. Push skipped because -NoPush was set."
    exit 0
}

$branch = (git branch --show-current).Trim()
if ([string]::IsNullOrWhiteSpace($branch)) {
    throw "Cannot determine current branch."
}

git push -u origin $branch
Write-Host "Sync complete on branch '$branch'."
