@echo off
REM Chrome Cookie-Editor JSON -> Playwright 세션 변환
cd /d "%~dp0"
call .venv\Scripts\activate.bat
set /p COOKIE_FILE="쿠키 JSON 파일 경로를 입력하세요: "
python main.py --import-cookies "%COOKIE_FILE%"
echo.
echo 완료. assets\sessions\aliexpress_state.json 이 생성되었습니다.
pause
