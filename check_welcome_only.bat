@echo off
setlocal EnableExtensions
cd /d "%~dp0"
chcp 65001 >nul
if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] .venv not found. Run build_windows.bat once to install dependencies.
  pause
  exit /b 1
)
set "QT_QPA_PLATFORM=offscreen"
echo Checking welcome screen and layout on THIS Windows machine...
".venv\Scripts\python.exe" -m unittest discover -s tests -p "test_v087_localization.py" -v
if errorlevel 1 goto fail
".venv\Scripts\python.exe" -m unittest discover -s tests -p "test_v089_buildfix_regressions.py" -v
if errorlevel 1 goto fail
set "QT_QPA_PLATFORM="
echo.
echo [SUCCESS] Welcome and SQLite cleanup checks passed.
echo Next: run build_windows_offline.bat directly to build the one-file EXE.
pause
exit /b 0
:fail
set "QT_QPA_PLATFORM="
echo.
echo [FAILED] Save the log and report it before running the full build.
pause
exit /b 1
