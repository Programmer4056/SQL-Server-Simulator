@echo off
rem Shared Python interpreter detection for this project.
rem A stale "py -3" registration may point to a removed Python installation.
set "PYTHON_CMD="

rem Prefer a real python.exe on PATH (ignore broken Windows Store aliases).
python -c "import sys; assert (3, 10) <= sys.version_info[:2] < (3, 16)" >nul 2>nul
if not errorlevel 1 set "PYTHON_CMD=python"

rem If python.exe is missing, ask the launcher for specific installed versions.
rem Avoid py -3: it can choose a stale registered interpreter.
if not defined PYTHON_CMD (
  for %%V in (3.14 3.13 3.12 3.11 3.10 3.15) do (
    if not defined PYTHON_CMD (
      py -%%V -c "import sys; assert (3, 10) <= sys.version_info[:2] < (3, 16)" >nul 2>nul
      if not errorlevel 1 set "PYTHON_CMD=py -%%V"
    )
  )
)

rem Some installations expose python3 rather than python.
if not defined PYTHON_CMD (
  python3 -c "import sys; assert (3, 10) <= sys.version_info[:2] < (3, 16)" >nul 2>nul
  if not errorlevel 1 set "PYTHON_CMD=python3"
)

if not defined PYTHON_CMD (
  echo.
  echo [ERROR] No working Python 3.10 - 3.15 interpreter was found.
  echo The Windows Python launcher might still point to an uninstalled version.
  echo.
  echo Check these commands in Command Prompt:
  echo   python --version
  echo   py -0p
  echo   where python
  echo.
  echo Install or repair Python from https://www.python.org/downloads/windows/
  exit /b 1
)

echo [OK] Found a working Python interpreter:
%PYTHON_CMD% -c "import sys; print('    ' + sys.version.split()[0] + '  ' + sys.executable)"
exit /b 0
