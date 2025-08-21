# create_release_notes.ps1 - Create custom release notes
param(
    [Parameter(Mandatory=$true)]
    [string]$Version,
    [Parameter(Mandatory=$false)]
    [string]$Notes
)

$releaseNotesFile = "release_notes_$Version.md"

if ($Notes) {
    # Use provided notes
    $Notes | Out-File -FilePath $releaseNotesFile -Encoding UTF8
    Write-Host "✅ Release notes created: $releaseNotesFile" -ForegroundColor Green
} else {
    # Interactive mode
    Write-Host "✏️  Creating release notes for version $Version" -ForegroundColor Cyan
    Write-Host "Enter your release notes (press Enter twice when done):" -ForegroundColor Yellow
    Write-Host "Example format:" -ForegroundColor Gray
    Write-Host "## What's Changed" -ForegroundColor Gray
    Write-Host "- Added new completions endpoint" -ForegroundColor Gray
    Write-Host "- Fixed streaming issues" -ForegroundColor Gray
    Write-Host "- Improved error handling" -ForegroundColor Gray
    Write-Host ""
    
    $releaseNotes = @()
    do {
        $line = Read-Host
        if ($line -ne "") {
            $releaseNotes += $line
        }
    } while ($line -ne "")
    
    if ($releaseNotes.Count -eq 0) {
        Write-Host "No release notes provided. Exiting." -ForegroundColor Red
        exit 1
    }
    
    $releaseNotesText = $releaseNotes -join "`n"
    $releaseNotesText | Out-File -FilePath $releaseNotesFile -Encoding UTF8
    
    Write-Host "✅ Release notes created: $releaseNotesFile" -ForegroundColor Green
    Write-Host "Preview:" -ForegroundColor Cyan
    Write-Host "------------------------" -ForegroundColor Gray
    Write-Host $releaseNotesText -ForegroundColor White
    Write-Host "------------------------" -ForegroundColor Gray
}