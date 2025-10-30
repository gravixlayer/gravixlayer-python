# release.ps1 - Automated Release Script for GravixLayer
# Usage: 
#   Auto-detect from last commit: ./scripts/release.ps1
#   Manual: ./scripts/release.ps1 -Part patch|minor|major
#   Dry run: ./scripts/release.ps1 -DryRun

param(
    [Parameter(Mandatory=$false)]
    [ValidateSet("patch", "minor", "major")]
    [string]$Part,
    
    [Parameter(Mandatory=$false)]
    [switch]$DryRun
)

# Colors
$Blue = "Blue"
$Green = "Green" 
$Yellow = "Yellow"
$Red = "Red"
$Cyan = "Cyan"
$Gray = "Gray"

function Write-ColorHost($Message, $Color) {
    Write-Host $Message -ForegroundColor $Color
}

function Write-Header() {
    Write-ColorHost "========================================" $Blue
    Write-ColorHost " GravixLayer Release Script" $Blue
    Write-ColorHost "========================================" $Blue
}

function Write-Summary($CurrentVersion, $NewVersion, $ReleaseNotes) {
    Write-Host ""
    Write-ColorHost "========================================" $Green
    Write-ColorHost " Release Summary" $Green
    Write-ColorHost "========================================" $Green
    Write-ColorHost "Previous Version: $CurrentVersion" $Cyan
    Write-ColorHost "New Version: $NewVersion" $Cyan
    Write-ColorHost "Release Notes: $ReleaseNotes" $Cyan
    Write-ColorHost "========================================" $Green
}

function Get-VersionPart($CommitMessage) {
    $CommitMessage = $CommitMessage.Trim()
    if ($CommitMessage -match "^(patch|minor|major):\s*(.+)") {
        $result = @{
            Part = $matches[1]
            Notes = $matches[2].Trim()
        }
        return $result
    }
    return $null
}

function Bump-Version($CurrentVersion, $Part) {
    $parts = $CurrentVersion.Split('.')
    $major = [int]$parts[0]
    $minor = [int]$parts[1]
    $patch = [int]$parts[2]
    
    switch ($Part) {
        "major" { 
            $major++
            $minor = 0
            $patch = 0
        }
        "minor" { 
            $minor++
            $patch = 0
        }
        "patch" { 
            $patch++
        }
    }
    
    return "$major.$minor.$patch"
}

function Update-VersionInFile($FilePath, $NewVersion) {
    if (-not (Test-Path $FilePath)) {
        Write-ColorHost "File not found: $FilePath" $Yellow
        return $false
    }
    
    $content = Get-Content $FilePath -Raw
    
    if ($FilePath -like "*version.py") {
        $content = $content -replace '__version__ = ".*"', "__version__ = ""$NewVersion"""
    }
    elseif ($FilePath -like "*__init__.py") {
        $content = $content -replace '__version__ = ".*"', "__version__ = ""$NewVersion"""
    }
    elseif ($FilePath -like "*setup.py") {
        $content = $content -replace 'version=".*"', "version=""$NewVersion"""
    }
    elseif ($FilePath -like "*pyproject.toml") {
        $content = $content -replace 'version = ".*"', "version = ""$NewVersion"""
    }
    
    Set-Content -Path $FilePath -Value $content -NoNewline
    return $true
}

# Main execution
Write-Header

if ($DryRun) {
    Write-Host ""
    Write-ColorHost "DRY RUN MODE - No changes will be made" $Yellow
    Write-Host ""
}

try {
    # Get current version
    Write-ColorHost "Getting current version..." $Green
    $CurrentVersion = python -c "import sys; sys.path.insert(0, '.'); from version import __version__; print(__version__)"
    
    if (-not $CurrentVersion) {
        Write-ColorHost "ERROR: Could not retrieve current version" $Red
        exit 1
    }
    
    Write-ColorHost "Current version: $CurrentVersion" $Green
    
    # Auto-detect version part from last commit if not provided
    if (-not $Part) {
        Write-Host ""
        Write-ColorHost "Auto-detecting version bump from last commit..." $Cyan
        $lastCommit = (git log -1 --pretty=%B).Trim()
        Write-ColorHost "Last commit: $lastCommit" $Gray
        
        try {
            $detected = Get-VersionPart $lastCommit
            
            if ($detected -and $detected.Part) {
                $Part = $detected.Part
                $ReleaseNotes = $detected.Notes
                Write-ColorHost "Detected: $Part release" $Green
                Write-ColorHost "Release notes: $ReleaseNotes" $Green
            }
            else {
                Write-ColorHost "ERROR: Could not detect version part from commit message" $Red
                Write-ColorHost "Commit message format: patch|minor|major: your message" $Yellow
                Write-ColorHost "Example: patch: fixed sandbox logic" $Yellow
                exit 1
            }
        }
        catch {
            Write-ColorHost "ERROR: Failed to parse commit message: $($_.Exception.Message)" $Red
            exit 1
        }
    }
    else {
        # Manual mode - get release notes from user
        Write-Host ""
        Write-ColorHost "Enter release notes for $Part release:" $Cyan
        $ReleaseNotes = Read-Host
        if (-not $ReleaseNotes) {
            $ReleaseNotes = "Version bump"
        }
    }
    
    # Calculate new version
    $NewVersion = Bump-Version $CurrentVersion $Part
    Write-Host ""
    Write-ColorHost "Version bump: $CurrentVersion -> $NewVersion" $Green
    
    if ($DryRun) {
        Write-Host ""
        Write-ColorHost "[DRY RUN] Would update version files..." $Yellow
        Write-ColorHost "[DRY RUN] Would create commit and tag v$NewVersion" $Yellow
        Write-ColorHost "[DRY RUN] Would push to remote" $Yellow
        Write-ColorHost "[DRY RUN] Would create GitHub release" $Yellow
        Write-Summary $CurrentVersion $NewVersion $ReleaseNotes
        Write-Host ""
        Write-ColorHost "Dry run completed successfully!" $Green
        exit 0
    }
    
    # Update version in all files
    Write-Host ""
    Write-ColorHost "Updating version files..." $Green
    $filesToUpdate = @(
        "version.py",
        "gravixlayer\__init__.py",
        "setup.py",
        "pyproject.toml"
    )
    
    foreach ($file in $filesToUpdate) {
        if (Update-VersionInFile $file $NewVersion) {
            Write-ColorHost "  Updated $file" $Gray
        }
    }
    
    # Git operations
    Write-Host ""
    Write-ColorHost "Creating git commit and tag..." $Green
    git add .
    $commitMsg = "Bump version: $CurrentVersion -> $NewVersion"
    git commit -m $commitMsg
    
    if ($LASTEXITCODE -ne 0) {
        Write-ColorHost "ERROR: Failed to create commit" $Red
        exit 1
    }
    
    git tag "v$NewVersion"
    
    if ($LASTEXITCODE -ne 0) {
        Write-ColorHost "ERROR: Failed to create tag" $Red
        exit 1
    }
    
    Write-ColorHost "  Created commit and tag v$NewVersion" $Gray
    
    # Push to remote
    Write-Host ""
    Write-ColorHost "Pushing to remote..." $Green
    git push origin main 2>&1 | Out-Null
    
    if ($LASTEXITCODE -ne 0) {
        Write-ColorHost "  WARNING: Failed to push to main" $Yellow
    }
    else {
        Write-ColorHost "  Pushed to main" $Gray
    }
    
    # Push tags
    git push origin "v$NewVersion" 2>&1 | Out-Null
    
    if ($LASTEXITCODE -ne 0) {
        Write-ColorHost "  WARNING: Failed to push tag" $Yellow
    }
    else {
        Write-ColorHost "  Pushed tag v$NewVersion" $Gray
    }
    
    # Wait for GitHub
    Write-Host ""
    Write-ColorHost "Waiting for GitHub to process..." $Yellow
    Start-Sleep -Seconds 3
    
    # Create GitHub release
    Write-ColorHost "Creating GitHub release..." $Green
    
    $ghCheck = gh --version 2>$null
    if ($ghCheck) {
        try {
            gh release create "v$NewVersion" --title "Release v$NewVersion" --notes "$ReleaseNotes" --latest 2>&1 | Out-Null
            Write-ColorHost "  GitHub release created" $Gray
            
            gh workflow run "pypi-release.yml" --ref "v$NewVersion" 2>&1 | Out-Null
            Write-ColorHost "  GitHub Actions triggered" $Gray
        }
        catch {
            Write-ColorHost "  WARNING: GitHub CLI operations failed" $Yellow
        }
    }
    else {
        Write-ColorHost "  GitHub CLI not found (install: winget install GitHub.cli)" $Gray
    }
    
    # Success
    Write-Host ""
    Write-ColorHost "Release process completed!" $Green
    Write-ColorHost "GitHub Actions will build and publish to PyPI" $Green
    
    Write-Host ""
    Write-ColorHost "Verification Links:" $Cyan
    Write-ColorHost "  Actions: https://github.com/gravixlayer/gravixlayer-python/actions" $Gray
    Write-ColorHost "  Releases: https://github.com/gravixlayer/gravixlayer-python/releases" $Gray
    Write-ColorHost "  PyPI: https://pypi.org/project/gravixlayer/" $Gray
    
    Write-Summary $CurrentVersion $NewVersion $ReleaseNotes
    
    Write-Host ""
    Write-ColorHost "Next Steps:" $Cyan
    Write-ColorHost "  1. Check GitHub Actions for build status" $Gray
    Write-ColorHost "  2. Verify release on GitHub" $Gray
    Write-ColorHost "  3. Test: pip install gravixlayer==$NewVersion" $Gray
    Write-Host ""

}
catch {
    Write-Host ""
    $errorMsg = $_.Exception.Message
    Write-ColorHost "ERROR: $errorMsg" $Red
    exit 1
}

exit 0
