# release.ps1 - PowerShell version of release script
param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("patch", "minor", "major")]
    [string]$Part
)

Write-Host "========================================" -ForegroundColor Blue
Write-Host " GravixLayer Release Script" -ForegroundColor Blue  
Write-Host "========================================" -ForegroundColor Blue

# Get current version
$CurrentVersion = python -c "import sys; sys.path.insert(0, '.'); from version import __version__; print(__version__)"
Write-Host "Current version: $CurrentVersion" -ForegroundColor Green

# Install bump2version if needed
try {
    bump2version --version | Out-Null
} catch {
    Write-Host "Installing bump2version..." -ForegroundColor Green
    pip install bump2version
}

# Bump version
Write-Host "Bumping $Part version..." -ForegroundColor Green
python scripts/bump_version.py $Part

if ($LASTEXITCODE -eq 0) {
    # Get new version
    $NewVersion = python -c "import sys; sys.path.insert(0, '.'); from version import __version__; print(__version__)"
    Write-Host "Version bumped: $CurrentVersion -> $NewVersion" -ForegroundColor Green
    
    # Push changes
    Write-Host "Pushing changes to remote..." -ForegroundColor Green
    git push
    git push --tags
    
    Write-Host "✅ Release process completed!" -ForegroundColor Green
    Write-Host "🚀 GitHub Actions will now build and publish to PyPI" -ForegroundColor Green
} else {
    Write-Host "❌ Version bump failed!" -ForegroundColor Red
}
