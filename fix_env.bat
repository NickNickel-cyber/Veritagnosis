@echo off
REM ===================================================================
REM  Environment check and repair.
REM
REM  Run this when the app fails at startup with a ModuleNotFoundError
REM  such as "No module named 'starlette'".
REM
REM  It answers the question that error does not: which Python is
REM  actually doing the importing. A package can be sitting perfectly
REM  installed in .venv\Lib\site-packages and still be invisible, if
REM  the interpreter running is not the one that owns that venv.
REM
REM  If the venv really is missing packages, this reinstalls them.
REM ===================================================================
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\activate.bat" (
  echo.
  echo   Could not find .venv in this folder.
  echo   Create it once with:
  echo.
  echo       py -m venv .venv
  echo       .venv\Scripts\activate
  echo       pip install -r requirements.txt
  echo.
  pause
  exit /b 1
)

call ".venv\Scripts\activate.bat"

python scripts\check_env.py
set "RC=%ERRORLEVEL%"

echo.
if "%RC%"=="0" (
  echo   Environment is good. Start the app with:  run.bat
) else (
  echo   Something above still needs attention.
)
echo.
pause
exit /b %RC%
