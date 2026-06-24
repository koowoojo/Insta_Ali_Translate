@echo off
chcp 65001 >nul
cd /d "%~dp0"
call .venv\Scripts\activate.bat

REM Usage: drag cookies.json onto this file, or run without args for defaults
set "COOKIE_FILE=%~1"
if "%COOKIE_FILE%"=="" if exist "%USERPROFILE%\Downloads\cookies.json" set "COOKIE_FILE=%USERPROFILE%\Downloads\cookies.json"
if "%COOKIE_FILE%"=="" if exist "%~dp0cookies.json" set "COOKIE_FILE=%~dp0cookies.json"
if "%COOKIE_FILE%"=="" (
  echo.
  echo [ERROR] Cookie JSON path required.
  echo.
  echo How to export ^(Chrome Cookie-Editor extension^):
  echo   1. Login at https://ko.aliexpress.com
  echo   2. Open Cookie-Editor on that tab
  echo   3. Export -^> JSON array ^(NOT encrypted backup^)
  echo   4. Drag the .json file onto this .bat
  echo.
  pause
  exit /b 1
)

echo Importing: %COOKIE_FILE%
python main.py --import-cookies "%COOKIE_FILE%"
if errorlevel 1 (
  echo.
  echo [FAILED] See error above. Re-export as plain JSON from Cookie-Editor.
  pause
  exit /b 1
)

echo.
echo [OK] Session saved: assets\sessions\aliexpress_state.json
pause
