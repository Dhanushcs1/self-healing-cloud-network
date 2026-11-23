@echo off
:: Setup custom domain mapping for Self-Healing Cloud Network
:: Maps selfhealing.local to 127.0.0.1 in the Windows hosts file

echo ========================================================
echo  Self-Healing Cloud Network - Custom Domain Setup
echo ========================================================
echo.

set HOSTS_FILE=%WINDIR%\System32\drivers\etc\hosts
set DOMAIN_ENTRY=127.0.0.1 selfhealing.local

findstr /i "selfhealing.local" "%HOSTS_FILE%" >nul 2>&1
if %errorlevel% == 0 (
    echo [OK] Custom domain 'selfhealing.local' is already configured in hosts file.
) else (
    echo Adding '127.0.0.1 selfhealing.local' to hosts file...
    echo %DOMAIN_ENTRY% >> "%HOSTS_FILE%"
    if %errorlevel% == 0 (
        echo [SUCCESS] Custom domain mapped: http://selfhealing.local:5000
    ) else (
        echo [NOTICE] Administrator privileges required to edit hosts file automatically.
        echo Please run this batch file as Administrator, or manually add:
        echo   127.0.0.1 selfhealing.local
        echo to: %HOSTS_FILE%
    )
)

echo.
echo Dashboard URL: http://selfhealing.local:5000
echo ========================================================
pause
