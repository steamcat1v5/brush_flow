@echo off
:: chcp 65001 >nul
title BrushFlow Runner

echo ==========================================
echo     BrushFlow 一键启动脚本 (Windows)
echo ==========================================

:: 检查后端虚拟环境
if not exist "backend\.venv" (
    echo [错误] 未发现后端虚拟环境，请先进入 backend 目录并按照 README 初始化。
    pause
    exit /b
)

:: 启动后端 (新窗口)
echo [1/2] 正在启动后端服务 端口 8000
start "BrushFlow Backend" cmd /k "cd backend && .venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000"

:: 等待后端启动
timeout /t 3 /nobreak >nul

:: 启动前端 (新窗口)
echo [2/2] 正在启动前端开发服务器 端口 3000
:: 优先使用 yarn，如果没有则尝试 npm
where yarn >nul 2>nul
if %ERRORLEVEL% equ 0 (
    start "BrushFlow Frontend" cmd /k "cd frontend && yarn dev"
) else (
    start "BrushFlow Frontend" cmd /k "cd frontend && npm run dev"
)

echo.
echo ==========================================
echo 启动完成！
echo 后端 API: http://localhost:8000
echo 前端界面: http://localhost:3000
echo ==========================================
echo.
echo 提示：如果要停止服务，请直接关闭弹出的两个黑窗口。
pause
