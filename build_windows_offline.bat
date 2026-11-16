@echo off
setlocal EnableExtensions
cd /d "%~dp0"
chcp 65001 >nul

echo ================================================================
echo   SQL Server Simulator 0.8.9 - Portable Offline Windows Builder
echo   Designed and developed by Ali Sayyadi
echo ================================================================
echo.
echo This builder runs on the developer's Windows PC, NOT on student PCs.
echo The finished EXE includes Python, PySide6 and required Qt libraries.
echo.

set "VENV_PY=.venv\Scripts\python.exe"
if not exist "%VENV_PY%" goto missing_deps
"%VENV_PY%" -c "import PySide6.QtWidgets, PyInstaller" >nul 2>nul
if errorlevel 1 goto missing_deps

set "QT_QPA_PLATFORM=offscreen"
echo [1/3] Checking regression tests, including Qt UI...
"%VENV_PY%" -m unittest discover -s tests -p "test_*.py" -v
if errorlevel 1 (
  set "QT_QPA_PLATFORM="
  goto failed
)
set "QT_QPA_PLATFORM="

echo [2/3] Building a SINGLE self-contained EXE for Windows x64...
"%VENV_PY%" -m PyInstaller --noconfirm --clean --onefile --windowed --noupx ^
 --name SQLServerSimulator_Offline_v0.8.9 --exclude-module tkinter ^
 --icon "%CD%\assets\app.ico" --add-data "%CD%\assets;assets" ^
 --distpath dist_offline --workpath build_offline --specpath build_offline ^
 src\main.py
if errorlevel 1 goto failed

if not exist "dist_offline\SQLServerSimulator_Offline_v0.8.9.exe" goto failed

echo [3/3] Completed. This file is for OFFLINE student use:
echo   dist_offline\SQLServerSimulator_Offline_v0.8.9.exe
echo The student needs neither Python nor pip nor SQL Server.
echo Test the EXE on a clean, offline Windows machine before releasing it.
echo.
pause
exit /b 0

:missing_deps
echo [ERROR] Missing local build dependencies. NO downloads were attempted.
echo On YOUR developer PC, run build_windows.bat once with Internet access.
echo Then run build_windows_offline.bat again.
pause
exit /b 1

:failed
echo [ERROR] Build/tests failed. Review the messages above.
echo Do not disable antivirus software to force the build.
pause
exit /b 1
