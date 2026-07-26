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

rem ---------- 先安装轻量依赖（chromadb, scikit-learn）----------
echo [1/3] Installing light dependencies...
"%PYTHON_CMD%" -m pip install chromadb scikit-learn ^
    -i https://pypi.tuna.tsinghua.edu.cn/simple ^
    --trusted-host pypi.tuna.tsinghua.edu.cn ^
    --default-timeout=1000 --retries=5 --prefer-binary
if %errorlevel% neq 0 (
    echo [WARN] 清华镜像失败，尝试阿里云镜像...
    "%PYTHON_CMD%" -m pip install chromadb scikit-learn ^
        -i https://mirrors.aliyun.com/pypi/simple ^
        --trusted-host mirrors.aliyun.com ^
        --default-timeout=1000 --retries=5 --prefer-binary
    if %errorlevel% neq 0 (
        echo [ERROR] 轻量依赖安装失败。
        pause
        exit /b 1
    )
)

rem ---------- 单独安装 torch CPU 版（从 PyTorch 官方源，比 PyPI 快且小）----------
echo [2/3] Installing PyTorch (CPU only, ~200MB)...
echo       (This may take a few minutes, please be patient)
"%PYTHON_CMD%" -m pip install torch --index-url https://download.pytorch.org/whl/cpu ^
    --default-timeout=1000 --retries=5
if %errorlevel% neq 0 (
    echo [WARN] PyTorch 官方源失败，尝试从镜像源安装...
    "%PYTHON_CMD%" -m pip install torch ^
        -i https://pypi.tuna.tsinghua.edu.cn/simple ^
        --trusted-host pypi.tuna.tsinghua.edu.cn ^
        --default-timeout=1000 --retries=5 --prefer-binary
    if %errorlevel% neq 0 (
        echo [ERROR] PyTorch 安装失败。
        pause
        exit /b 1
    )
)

rem ---------- 安装 sentence-transformers（现在 torch 已有，会快很多）----------
echo [3/3] Installing sentence-transformers...
"%PYTHON_CMD%" -m pip install sentence-transformers ^
    -i https://pypi.tuna.tsinghua.edu.cn/simple ^
    --trusted-host pypi.tuna.tsinghua.edu.cn ^
    --default-timeout=1000 --retries=5 --prefer-binary
if %errorlevel% neq 0 (
    echo [WARN] 清华镜像失败，尝试阿里云镜像...
    "%PYTHON_CMD%" -m pip install sentence-transformers ^
        -i https://mirrors.aliyun.com/pypi/simple ^
        --trusted-host mirrors.aliyun.com ^
        --default-timeout=1000 --retries=5 --prefer-binary
    if %errorlevel% neq 0 (
        echo [ERROR] sentence-transformers 安装失败。
        pause
        exit /b 1
    )
)

rem ---------- 4. 执行初始化脚本（建目录 + 下载嵌入模型 ~188MB）----------
echo.
echo [4/4] Running initialization (downloading embedding model ~188MB)...
echo       (This may take a few minutes on first run, model will be cached)
"%PYTHON_CMD%" "%~dp0init.py"
if %errorlevel% neq 0 (
    echo.
    echo [WARN] 初始化脚本执行失败，但依赖已安装成功。
    echo        你可以稍后手动运行: python scripts/init.py
)

echo.
echo ============================================
echo  [DONE] Installation successful!
echo  Next step: Switch Workbuddy to Craft mode
echo  and import extractExp/SKILL.md
echo  Then say: 设置萃取经验助手路径为 D:/extractExp
echo ============================================
echo.
pause
