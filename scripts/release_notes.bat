@echo off
REM Create release notes for a version
REM Usage: release_notes.bat <version> [notes]

if "%~1"=="" (
    echo Usage: release_notes.bat ^<version^> [notes]
    echo Example: release_notes.bat 0.0.16 "Added new features and bug fixes"
    exit /b 1
)

set VERSION=%~1
set NOTES=%~2

if "%NOTES%"=="" (
    powershell -ExecutionPolicy Bypass -File scripts/create_release_notes.ps1 -Version %VERSION%
) else (
    powershell -ExecutionPolicy Bypass -File scripts/create_release_notes.ps1 -Version %VERSION% -Notes "%NOTES%"
)