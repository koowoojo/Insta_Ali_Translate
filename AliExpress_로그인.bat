@echo off
REM AliExpress Playwright 로그인 세션 저장
cd /d "%~dp0"
call .venv\Scripts\activate.bat
python main.py --login
pause
