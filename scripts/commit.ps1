# commit.ps1 - Helper script for creating release commits
# Usage: ./scripts/commit.ps1 -Type patch|minor|major -Message "your message"

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("patch", "minor", "major")]
    [string]$Type,
    
    [Parameter(Mandatory=$true)]
    [string]$Message
)

$commitMessage = "${Type}: $Message"

Write-Host "Creating commit with message:" -ForegroundColor Cyan
Write-Host "  $commitMessage" -ForegroundColor White

git add .
git commit -m $commitMessage

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n✅ Commit created successfully!" -ForegroundColor Green
    Write-Host "`nTo release, run:" -ForegroundColor Yellow
    Write-Host "  ./scripts/release.ps1" -ForegroundColor Cyan
    Write-Host "`nOr for dry run:" -ForegroundColor Yellow
    Write-Host "  ./scripts/release.ps1 -DryRun" -ForegroundColor Cyan
}
else {
    Write-Host "`n❌ Commit failed!" -ForegroundColor Red
    exit 1
}
