@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 翻译 Agent

echo =============================================
echo   翻译 Agent - 启动中
echo   首次启动若提示安装依赖，请稍候片刻
echo =============================================
echo.

rem ---- 检查内置运行环境 ----
if not exist "runtime\python.exe" (
    echo [错误] 未找到内置运行环境 runtime，请确保解压的是完整版本。
    echo [错误] 请重新下载完整包后解压使用。
    pause
    exit /b 1
)

rem ---- 首次运行: 自动安装依赖 ----
if not exist "runtime\Lib\site-packages\flask" (
    echo [提示] 首次运行，正在自动安装依赖(需要网络)...
    echo.
    "runtime\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo [错误] 依赖安装失败，请检查网络连接后重新启动。
        pause
        exit /b 1
    )
    echo [完成] 依赖安装完成。
)

echo.
echo 服务启动中... 请稍候，浏览器将自动打开
echo 地址: http://localhost:5000
echo 关闭本窗口即停止服务
echo.

rem ---- 延迟 4 秒后自动打开浏览器 ----
start "" /b cmd /c "timeout /t 4 /nobreak >nul & start "" http://localhost:5000"

rem ---- 启动服务 ----
"runtime\python.exe" run.py

echo.
echo 服务已停止。
pause
