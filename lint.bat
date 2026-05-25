@echo off
:: 1. Capture the directory the user is currently in
set "USER_EXEC_DIR=%cd%"

:: 2. Switch to project root so imports and .env load safely
set "PROJECT_ROOT=%~dp0"
cd /d "%PROJECT_ROOT%"

:: 3. Pass the original directory to Python via an environment variable
set "LINT_WORKSPACE=%USER_EXEC_DIR%"

"%PROJECT_ROOT%\.venv\Scripts\python.exe" launcher.py %*