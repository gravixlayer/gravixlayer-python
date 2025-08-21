# release.ps1 - Enhanced PowerShell release script for GravixLayer
param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("patch", "minor", "major")]
    [string]$Part
)

# Colors and formatting
$Blue = "Blue"
$Green = "Green" 
$Yellow = "Yellow"
$Red = "Red"
$Cyan = "Cyan"

function Write-ColorHost($Message, $Color) {
    if ([string]::IsNullOrEmpty($Color)) {
        Write-Host $Message
    } else {
        Write-Host $Message -ForegroundColor $Color
    }
}

function Write-Header() {
    Write-ColorHost "========================================" $Blue
    Write-ColorHost " GravixLayer Release Script" $Blue
    Write-ColorHost "========================================" $Blue
}

function Write-Summary($CurrentVersion, $NewVersion) {
    Write-ColorHost "========================================" $Blue
    Write-ColorHost " Release Summary" $Blue
    Write-ColorHost "========================================" $Blue
    Write-ColorHost "Previous Version: $CurrentVersion" $Green
    Write-ColorHost "New Version: $NewVersion" $Green
    Write-ColorHost "Tag: v$NewVersion" $Green
    Write-ColorHost "========================================" $Blue
}

# Main script execution
Write-Header

try {
    # Get current version
    Write-ColorHost "Getting current version..." $Green
    $CurrentVersion = python -c "import sys; sys.path.insert(0, '.'); from version import __version__; print(__version__)"
    
    if (-not $CurrentVersion) {
        Write-ColorHost "ERROR: Could not retrieve current version" $Red
        exit 1
    }
    
    Write-ColorHost "Current version: $CurrentVersion" $Green
    
    # Check if working directory has uncommitted changes
    Write-ColorHost "Checking for uncommitted changes..." $Yellow
    $gitStatus = git status --porcelain
    if ($gitStatus) {
        Write-ColorHost "Found uncommitted changes. Committing them..." $Yellow
        git add .
        git commit -m "Pre-release: commit changes before version bump"
        if ($LASTEXITCODE -ne 0) {
            Write-ColorHost "ERROR: Failed to commit changes" $Red
            exit 1
        }
    }
    
    # Install bump2version if needed
    Write-ColorHost "Checking for bump2version..." $Green
    try {
        $null = bump2version --version 2>$null
        Write-ColorHost "bump2version found" $Green
    } catch {
        Write-ColorHost "Installing bump2version..." $Yellow
        pip install bump2version
        if ($LASTEXITCODE -ne 0) {
            Write-ColorHost "ERROR: Failed to install bump2version" $Red
            exit 1
        }
    }
    
    # Bump version using our custom script
    Write-ColorHost "Bumping $Part version..." $Green
    python scripts/bump_version.py $Part
    
    if ($LASTEXITCODE -ne 0) {
        Write-ColorHost "ERROR: Version bump failed!" $Red
        exit 1
    }
    
    # Get new version for release notes
    $NewVersion = python -c "import sys; sys.path.insert(0, '.'); from version import __version__; print(__version__)"
    
    # Prompt user for custom release notes
    Write-ColorHost "✏️  Please enter release notes for version $NewVersion" $Cyan
    Write-ColorHost "Enter your release notes (press Enter twice when done):" $Yellow
    Write-ColorHost "Example: 'Added new completions endpoint, Fixed streaming issues, Improved error handling'" $Gray
    Write-ColorHost ""
    
    $releaseNotes = @()
    do {
        $line = Read-Host
        if ($line -ne "") {
            $releaseNotes += $line
        }
    } while ($line -ne "")
    
    if ($releaseNotes.Count -eq 0) {
        Write-ColorHost "No release notes provided. Using default message." $Yellow
        $releaseNotesText = "Version $NewVersion release with updates and improvements."
    } else {
        $releaseNotesText = $releaseNotes -join "`n"
    }
    
    Write-ColorHost "✅ Release notes saved" $Green
    Write-ColorHost "Release notes preview:" $Cyan
    Write-ColorHost "------------------------" $Gray
    Write-ColorHost $releaseNotesText $White
    Write-ColorHost "------------------------" $Gray
    
    Write-ColorHost "Version successfully bumped: $CurrentVersion -> $NewVersion" $Green
    
    # Create a temporary environment variable for GitHub Actions
    $env:RELEASE_NOTES = $releaseNotesText
    
    # Push changes to remote
    Write-ColorHost "Pushing changes to remote repository..." $Green
    git push origin main
    if ($LASTEXITCODE -ne 0) {
        Write-ColorHost "WARNING: Failed to push changes to main branch" $Yellow
    }
    
    # Push tags to remote
    Write-ColorHost "Pushing tags to remote repository..." $Green
    git push origin --tags
    if ($LASTEXITCODE -ne 0) {
        Write-ColorHost "WARNING: Failed to push tags" $Yellow
    }
    
    # Wait for GitHub to process the tag
    Write-ColorHost "Waiting for GitHub to process the new tag..." $Yellow
    Start-Sleep -Seconds 5
    
    # Try to use GitHub CLI for additional operations
    Write-ColorHost "Attempting to trigger GitHub Actions and create release..." $Green
    
    try {
        # Check if GitHub CLI is available
        $ghCheck = gh --version 2>$null
        if ($ghCheck) {
            Write-ColorHost "GitHub CLI found. Creating release with custom notes..." $Green
            
            # Create GitHub release with custom notes
            try {
                $escapedNotes = $releaseNotesText -replace '"', '\"'
                gh release create "v$NewVersion" --title "Release v$NewVersion" --notes "$escapedNotes" --latest
                Write-ColorHost "SUCCESS: GitHub release created!" $Green
            } catch {
                Write-ColorHost "WARNING: Could not create GitHub release automatically" $Yellow
            }
            
            # Trigger workflow manually
            try {
                gh workflow run "pypi-release.yml" --ref "v$NewVersion"
                Write-ColorHost "SUCCESS: GitHub Actions workflow triggered!" $Green
            } catch {
                Write-ColorHost "WARNING: Could not trigger workflow automatically" $Yellow
            }
            
        } else {
            Write-ColorHost "GitHub CLI not found." $Yellow
            Write-ColorHost "Install with: winget install GitHub.cli" $Cyan
            Write-ColorHost "Then run: gh auth login" $Cyan
        }
    } catch {
        Write-ColorHost "GitHub CLI operations failed: $($_.Exception.Message)" $Yellow
    }
    
    # Final success message and instructions
    Write-ColorHost "" 
    Write-ColorHost "SUCCESS: Release process completed!" $Green
    Write-ColorHost "GitHub Actions should build and publish to PyPI automatically." $Green
    Write-ColorHost "" 
    
    # Provide helpful links
    Write-ColorHost "Verification Links:" $Cyan
    Write-ColorHost "- GitHub Actions: https://github.com/gravixlayer/gravixlayer-python/actions" $Cyan
    Write-ColorHost "- GitHub Releases: https://github.com/gravixlayer/gravixlayer-python/releases" $Cyan
    Write-ColorHost "- PyPI Package: https://pypi.org/project/gravixlayer/" $Cyan
    Write-ColorHost "" 
    
    Write-Summary $CurrentVersion $NewVersion
    
    # Final check instructions
    Write-ColorHost "Next Steps:" $Yellow
    Write-ColorHost "1. Check GitHub Actions for build status" $Yellow
    Write-ColorHost "2. Verify release appears on GitHub Releases page" $Yellow
    Write-ColorHost "3. Confirm package is published to PyPI (may take a few minutes)" $Yellow
    Write-ColorHost "4. Test installation: pip install gravixlayer==$NewVersion" $Yellow

} catch {
    Write-ColorHost "FATAL ERROR: $($_.Exception.Message)" $Red
    Write-ColorHost "Stack Trace: $($_.ScriptStackTrace)" $Red
    exit 1
}

# Script completed successfully
exit 0