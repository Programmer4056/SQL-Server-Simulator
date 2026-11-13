@echo off
setlocal EnableExtensions
cd /d "%~dp0"
chcp 65001 >nul

echo ==================================================
echo  SQL Server Simulator 0.6.1 - Windows Builder FIX
echo  Designed and developed by Ali Sayyadi
echo ==================================================
echo.

call "%~dp0detect_python.bat"
if errorlevel 1 goto no_python

rem Use an isolated Python environment just for this project.
set "VENV_PY=.venv\Scripts\python.exe"
if exist "%VENV_PY%" (
  "%VENV_PY%" -c "import sys" >nul 2>nul
  if errorlevel 1 (
    echo [INFO] The old .venv points to a missing Python installation.
    echo [INFO] Renaming it and creating a fresh project environment.
    set "OLD_ENV=.venv_broken_%RANDOM%"
    call :backup_broken_venv
    if errorlevel 1 goto failed
  )
)
if not exist "%VENV_PY%" (
  echo [0/3] Creating a Python virtual environment...
  %PYTHON_CMD% -m venv ".venv"
  if errorlevel 1 goto failed
)
if not exist "%VENV_PY%" goto failed

echo [1/3] Installing PySide6 Essentials and PyInstaller...
"%VENV_PY%" -m pip install -r requirements.txt "pyinstaller>=6.8,<8"
if errorlevel 1 goto failed

echo [CHECK] Running core, identity, export and Qt regression tests...
set "QT_QPA_PLATFORM=offscreen"
"%VENV_PY%" -m unittest discover -s tests -p "test_*.py" -v
if errorlevel 1 (
  set "QT_QPA_PLATFORM="
  goto failed
)
set "QT_QPA_PLATFORM="

echo [2/3] Building the Qt Windows application...
"%VENV_PY%" -m PyInstaller --noconfirm --clean --windowed --onedir ^
 --name SQLServerSimulator --exclude-module tkinter ^
 --icon "%CD%\assets\app.ico" --add-data "%CD%\assets;assets" ^
 --distpath dist --workpath build --specpath build ^
 src\main.py
if errorlevel 1 goto failed

echo [3/3] Compiling the graphical installer...
set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" (
  echo.
  echo Application build succeeded, but Inno Setup 6 was not found.
  echo Your executable is at: dist\SQLServerSimulator\SQLServerSimulator.exe
  echo Install Inno Setup 6 from https://jrsoftware.org/isinfo.php
  echo Then re-run this file to create the Setup installer.
  pause
  exit /b 2
)
"%ISCC%" installer.iss
if errorlevel 1 goto failed

echo.
echo [SUCCESS] installer_out\SQL_Server_Simulator_Setup_v0.6.1.exe
pause
exit /b 0

:backup_broken_venv
move ".venv" "%OLD_ENV%" >nul
if errorlevel 1 (
  echo [ERROR] Could not rename the old .venv folder.
  exit /b 1
)
echo [INFO] Old environment saved as %OLD_ENV%
exit /b 0

:no_python
echo.
echo The build did not start because Python could not be found.
pause
exit /b 1

:failed
echo.
echo Build failed. Review the error messages above.
pause
exit /b 1
