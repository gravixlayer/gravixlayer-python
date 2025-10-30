# release-commit.ps1 - One command to commit and release
# Usage: ./scripts/release-commit.ps1 -Type patch|minor|major -Message "your message"

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("patch", "minor", "major")]
    [string]$Type,
    
    [Parameter(Mandatory=$true)]
    [string]$Message,
    
    [Parameter(Mandatory=$false)]
    [switch]$DryRun
)

$Blue = "Blue"
$Green = "Green"
$Yellow = "Yellow"
$Cyan = "Cyan"

Write-Host "========================================" -ForegroundColor $Blue
Write-Host " GravixLayer Release Commit" -ForegroundColor $Blue
Write-Host "========================================" -ForegroundColor $Blue
Write-Host ""

if ($DryRun) {
    Write-Host "DRY RUN MODE - No changes will be made" -ForegroundColor $Yellow
    Write-Host ""
}

$commitMessage = "${Type}: $Message"

Write-Host "Step 1: Creating commit..." -ForegroundColor $Cyan
Write-Host "  Message: $commitMessage" -ForegroundColor $Green

if (-not $DryRun) {
    git add .
    git commit -m $commitMessage
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to create commit!" -ForegroundColor Red
        exit 1
    }
    Write-Host "  Commit created" -ForegroundColor $Green
}
else {
    Write-Host "  [DRY RUN] Would create commit" -ForegroundColor $Yellow
}

Write-Host ""
Write-Host "Step 2: Running release process..." -ForegroundColor $Cyan

# In dry run, we need to pass the type manually since commit doesn't exist yet
if ($DryRun) {
    # Create a temporary commit to test
    git add . 2>&1 | Out-Null
    git commit -m $commitMessage 2>&1 | Out-Null
    
    & "$PSScriptRoot\release.ps1" -DryRun
    
    # Undo the temporary commit
    git reset HEAD~1 2>&1 | Out-Null
}
else {
    & "$PSScriptRoot\release.ps1"
}

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor $Green
    Write-Host " All Done!" -ForegroundColor $Green
    Write-Host "========================================" -ForegroundColor $Green
}
else {
    Write-Host ""
    Write-Host "Release process failed!" -ForegroundColor Red
    exit 1
}
