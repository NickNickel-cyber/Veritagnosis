@echo off
REM ===================================================================
REM  Deploy Veritagnosis to Reflex Cloud.
REM
REM    deploy.bat          push the current code live
REM    deploy.bat login    sign in first (once)
REM
REM  Reflex Cloud is the simplest option: it hosts both halves of the
REM  app for you, so there is no server to configure.
REM ===================================================================
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\activate.bat" (
  echo   No .venv here. Run run.bat first to set the project up.
  pause & exit /b 1
)
call ".venv\Scripts\activate.bat"
set "REFLEX_USE_NPM=1"
set "NODE_OPTIONS="

if /i "%~1"=="login" (
  reflex login
  pause & exit /b 0
)

echo.
echo   BEFORE YOU DEPLOY - read this once:
echo.
echo   1. Your .env is NOT uploaded (it is gitignored, on purpose).
echo      Set the same keys as secrets in the Reflex Cloud dashboard:
echo        VG_FIELD_KEY, VG_INDEX_KEY, VG_SMTP_USER, VG_SMTP_PASSWORD
echo      Use the SAME field key, or existing encrypted data is unreadable.
echo.
echo   2. SQLite lives in a file. On a host that restarts containers, that
echo      file can be wiped. Fine for testing; before real users, switch
echo      db_url in rxconfig.py to a hosted Postgres.
echo.
pause

reflex deploy
echo.
pause
