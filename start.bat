@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Synth Engine Local Development

echo ============================================
echo   Synth Engine 本地测试环境
echo   前端: http://127.0.0.1:3000/synth/
echo   后端: http://127.0.0.1:8080
echo   停止: Ctrl+C
echo ============================================

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_local.ps1"
set "exit_code=%errorlevel%"

if not "%exit_code%"=="0" (
    echo.
    echo [ERROR] 启动脚本异常退出，错误码 %exit_code%
    pause
)
exit /b %exit_code%
