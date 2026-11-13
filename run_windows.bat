@echo off
setlocal EnableExtensions
cd /d "%~dp0"
chcp 65001 >nul

echo SQL Server Simulator 0.6.1 - Run from source
call "%~dp0detect_python.bat"
if errorlevel 1 goto failed

set "VENV_PY=.venv\Scripts\python.exe"
if exist "%VENV_PY%" (
  "%VENV_PY%" -c "import sys" >nul 2>nul
  if errorlevel 1 (
    echo [INFO] Existing .venv is broken. Saving it and creating a fresh one.
    set "OLD_ENV=.venv_broken_%RANDOM%"
    call :backup_broken_venv
    if errorlevel 1 goto failed
  )
)
if not exist "%VENV_PY%" (
  %PYTHON_CMD% -m venv ".venv"
  if errorlevel 1 goto failed
)
if not exist "%VENV_PY%" goto failed

echo Installing app dependencies...
"%VENV_PY%" -m pip install -r requirements.txt
if errorlevel 1 goto failed

echo Launching SQL Server Simulator...
"%VENV_PY%" src\main.py
if errorlevel 1 goto failed
exit /b 0

:backup_broken_venv
move ".venv" "%OLD_ENV%" >nul
if errorlevel 1 exit /b 1
exit /b 0

:failed
echo.
echo Could not launch the program. See the error above.
pause
exit /b 1
