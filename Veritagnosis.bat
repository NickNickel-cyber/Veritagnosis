@echo off
REM ===================================================================
REM  Veritagnosis - double-click this on Windows.
REM
REM  It finds Python, sets the app up the first time, and starts it.
REM  Nothing else to install or configure.
REM
REM  Options, if you ever want them:
REM      Veritagnosis.bat dev     reload automatically while editing code
REM      Veritagnosis.bat reset   rebuild the web page from scratch
REM
REM  macOS users: use Veritagnosis.command instead.
REM ===================================================================
title Veritagnosis
cd /d "%~dp0"

REM The py launcher ships with the official python.org installer and picks a
REM sensible version. Fall back to python on PATH.
where py >nul 2>&1 && (py -3 start.py %* & goto :done)
where python >nul 2>&1 && (python start.py %* & goto :done)

echo.
echo   Python is not installed on this computer.
echo.
echo   Veritagnosis needs it. Install Python 3.11 or newer:
echo.
echo       https://www.python.org/downloads/
echo.
echo   IMPORTANT: on the first screen of the installer, tick
echo   "Add python.exe to PATH". Then close this window, open
echo   this folder again, and double-click Veritagnosis.bat.
echo.
pause
exit /b 1

:done
REM start.py pauses on its own errors. This catches a hard crash so the
REM window does not vanish before the message can be read.
if errorlevel 1 pause
exit /b %errorlevel%
