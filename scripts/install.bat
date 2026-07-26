@echo off

echo ============================================
echo  extractExp Dependency Installer
echo ============================================
echo.

set "PYTHON_CMD="

rem ---------- 1. Try python in PATH ----------
where python >nul 2>&1
if %errorlevel%==0 (
    for /f "delims=" %%i in ('where python 2^>nul') do (
        echo %%i | findstr /i "WindowsApps" >nul 2>&1
        if errorlevel 1 (
            set "PYTHON_CMD=%%i"
            goto :found_python
        )
    )
)

rem ---------- 2. Try py launcher ----------
where py >nul 2>&1
if %errorlevel%==0 (
    set "PYTHON_CMD=py -3"
    goto :found_python
)

rem ---------- 3. Try Anaconda common paths ----------
if exist "%USERPROFILE%\Anaconda3\python.exe" (
    set "PYTHON_CMD=%USERPROFILE%\Anaconda3\python.exe"
    goto :found_python
)
if exist "C:\Anaconda3\python.exe" (
    set "PYTHON_CMD=C:\Anaconda3\python.exe"
    goto :found_python
)
if exist "C:\ProgramData\Anaconda3\python.exe" (
    set "PYTHON_CMD=C:\ProgramData\Anaconda3\python.exe"
    goto :found_python
)

rem ---------- 4. Try official Python common paths ----------
if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" (
    set "PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
    goto :found_python
)
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set "PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    goto :found_python
)
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    set "PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    goto :found_python
)
if exist "C:\Python313\python.exe" (
    set "PYTHON_CMD=C:\Python313\python.exe"
    goto :found_python
)
if exist "C:\Python312\python.exe" (
    set "PYTHON_CMD=C:\Python312\python.exe"
    goto :found_python
)

rem ---------- 5. Try Workbuddy built-in Python ----------
if exist "%USERPROFILE%\.workbuddy\binaries\python\versions\3.13.12\python.exe" (
    set "PYTHON_CMD=%USERPROFILE%\.workbuddy\binaries\python\versions\3.13.12\python.exe"
    goto :found_python
)
if exist "%USERPROFILE%\.workbuddy\binaries\python\envs\default\Scripts\python.exe" (
    set "PYTHON_CMD=%USERPROFILE%\.workbuddy\binaries\python\envs\default\Scripts\python.exe"
    goto :found_python
)

rem ---------- No Python found ----------
echo [ERROR] Python not found on this system.
echo.
echo Please install Python using one of these methods:
echo.
echo   Option A (recommended): Install Workbuddy - it includes a built-in Python.
echo   Option B: Download Python from https://www.python.org/downloads/
echo             NOTE: Check "Add Python to PATH" during installation.
echo   Option C: Install Anaconda from https://www.anaconda.com/download
echo.
echo Press any key to exit...
pause >nul
exit /b 1

:found_python
echo [OK] Using Python: %PYTHON_CMD%
"%PYTHON_CMD%" --version
echo.

echo Installing extractExp dependencies...
echo.
"%PYTHON_CMD%" -m pip install -r "%~dp0requirements.txt"
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Dependency installation failed.
    echo Please check your network connection and try again.
    pause
    exit /b 1
)

echo.
echo ============================================
echo  [DONE] Installation successful!
echo  Next step: Switch Workbuddy to Craft mode
echo  and import extractExp/SKILL.md
echo ============================================
echo.
pause
