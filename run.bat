@echo off
REM ===================================================================
REM  Veritagnosis - Windows launcher.
REM
REM  This file only finds Python and hands over to start.py, which is
REM  where all the real work lives. Keeping the logic in one place
REM  means Windows and macOS cannot drift apart, and it means the
REM  thing you run is the same thing that gets tested.
REM
REM      run.bat            start the app
REM      run.bat dev        start with hot reload
REM      run.bat reset      rebuild the web frontend from scratch
REM      run.bat check      set up and verify, without starting
REM      run.bat test       run the test suite
REM ===================================================================
setlocal
cd /d "%~dp0"

REM The py launcher ships with the official Windows installer and picks a
REM sensible version. Fall back to python on PATH if it is not there.
where py >nul 2>&1
if not errorlevel 1 (
  py -3 start.py %*
  goto :done
)

where python >nul 2>&1
if not errorlevel 1 (
  python start.py %*
  goto :done
)

echo.
echo   Python was not found on this computer.
echo.
echo   Install Python 3.11 or newer from:
echo       https://www.python.org/downloads/
echo.
echo   IMPORTANT: tick "Add python.exe to PATH" in the installer,
echo   then close this window, open a new one, and run this file again.
echo.
pause
exit /b 1

:done
REM start.py pauses on its own errors; this catches a hard crash so the
REM window does not vanish before the message can be read.
if errorlevel 1 pause
exit /b %errorlevel%
