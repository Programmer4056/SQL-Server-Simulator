@echo off
setlocal EnableExtensions
cd /d "%~dp0"
chcp 65001 >nul

echo =========================================================
echo SQL Server Simulator v0.8.9 - FAST START OFFLINE BUILDER
echo Developed by Ali Sayyadi
echo =========================================================
echo.
echo This builds an ONEDIR application; runtime files are NOT

echo extracted on every application launch.
echo No internet or pip install is used by this builder.
echo.

set "VENV_PY=%~dp0.venv\Scripts\python.exe"
if not exist "%VENV_PY%" goto missing_deps
"%VENV_PY%" -c "import PySide6.QtWidgets, PyInstaller" >nul 2>nul
if errorlevel 1 goto missing_deps

rem Run the focused v0.8.9 tests before creating the release.
set "QT_QPA_PLATFORM=offscreen"
echo [1/3] Running focused release tests...
"%VENV_PY%" -m unittest discover -s tests -p "test_v089*.py" -q
if errorlevel 1 (
  set "QT_QPA_PLATFORM="
  goto failed
)
set "QT_QPA_PLATFORM="

echo [2/3] Building the faster one-folder Windows executable...
"%VENV_PY%" -m PyInstaller --noconfirm --clean --onedir --windowed --noupx ^
 --name SQLServerSimulator --exclude-module tkinter ^
 --icon "%CD%\assets\app.ico" --add-data "%CD%\assets;assets" ^
 --distpath dist --workpath build_fast --specpath build_fast ^
 src\main.py
if errorlevel 1 goto failed
if not exist "dist\SQLServerSimulator\SQLServerSimulator.exe" goto failed

echo [OK] Portable FOLDER is ready:
echo      dist\SQLServerSimulator\
echo      Keep the entire folder, including _internal.
echo.

rem An Inno Setup installer gives students ONE offline Setup.exe, but
rem installs the onedir payload once instead of extracting on every run.
echo [3/3] Checking for the optional Inno Setup compiler...
set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not defined ISCC goto no_installer

"%ISCC%" "%CD%\installer.iss"
if errorlevel 1 goto installer_failed
if not exist "installer_out\SQL_Server_Simulator_Setup_v0.8.9.exe" goto installer_failed

echo.
echo [SUCCESS] ONE offline Setup.exe for students:
echo      installer_out\SQL_Server_Simulator_Setup_v0.8.9.exe
echo Install once, then start the app from its shortcut.
echo No Python, PySide6, SQL Server or internet needed at runtime.
echo.
pause
exit /b 0

:no_installer
echo.
echo [SUCCESS] The fast portable folder was built successfully.
echo To also build a SINGLE offline Setup.exe, install Inno Setup 6

echo on this developer PC, then run this BAT file again.
echo No installer is needed to try the fast one-folder version.
echo.
pause
exit /b 0

:installer_failed
echo.
echo [WARNING] Portable folder is ready, but installer creation failed.
echo See Inno Setup errors above; the working EXE remains in dist.
echo.
pause
exit /b 2

:missing_deps
echo.
echo [ERROR] Project's .venv / PySide6 / PyInstaller missing.
echo On the developer computer, run build_windows.bat first.
echo This BAT never downloads dependencies.
echo.
pause
exit /b 1

:failed
echo.
echo [ERROR] Tests or fast build failed. Nothing was published.
echo Review the error messages above.
echo.
pause
exit /b 1
