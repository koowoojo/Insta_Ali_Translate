@echo off
chcp 65001 >nul
cd /d "%~dp0"
call .venv\Scripts\activate.bat

set "CHROME=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME%" set "CHROME=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME%" (
  echo [ERROR] Google Chrome not found.
  pause
  exit /b 1
)

echo.
echo === AliExpress session via Chrome CDP ===
echo.
echo Step 1: Opening Chrome debug window...
echo         Login at https://ko.aliexpress.com in that window.
echo.

start "" "%CHROME%" --remote-debugging-port=9222 --user-data-dir="%TEMP%\chrome-ali-session" "https://ko.aliexpress.com/"

echo Step 2: After login, press any key here to save session...
pause >nul

python main.py --capture-cdp
if errorlevel 1 (
  echo [FAILED] Could not capture session. Is Chrome still open with port 9222?
  pause
  exit /b 1
)

echo.
echo [OK] Session saved: assets\sessions\aliexpress_state.json
pause
