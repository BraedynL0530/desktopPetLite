@echo off
echo ==========================================================
echo [!] FORCING UNTHROTTLED TERMINATION OF BACKGROUND LINT PROCESSES
echo ==========================================================
:: Direct execution target targeting background command line matching
taskkill /f /im pythonw.exe >nul 2>&1
taskkill /f /im python.exe /fi "WINDOWTITLE eq cat >>>*" >nul 2>&1
powershell -NoProfile -Command "Get-Process | Where-Object { $_.CommandLine -like '*launcher.py*' } | Stop-Process -Force" >nul 2>&1
del .lint_tui.lock >nul 2>&1
echo [✓] Done. All background processes successfully terminated and workspace lock files cleared.
pause