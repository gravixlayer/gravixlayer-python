@echo off
REM Quick changelog entry script for Windows
REM Usage: changelog.bat "Your message here" [type]

if "%~1"=="" (
    echo Usage: changelog.bat "Your message here" [added^|changed^|fixed^|removed^|security]
    echo Example: changelog.bat "Fixed bug in API" fixed
    exit /b 1
)

set MESSAGE=%~1
set TYPE=%~2

if "%TYPE%"=="" set TYPE=changed

python scripts/add_changelog_entry.py "%MESSAGE%" --type %TYPE%