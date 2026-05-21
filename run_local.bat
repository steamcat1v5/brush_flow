@echo off
chcp 65001 >nul
title BrushFlow Runner

echo ==========================================
echo     BrushFlow 一键启动脚本 (Windows)
echo ==========================================

:: 检查环境变量文件
if not exist ".env" (
    echo [信息] 未找到 .env 文件，正在从 .env.example 复制...
    copy .env.example .env >nul
)

:: 检查后端环境
if not exist "backend\.venv" (
    echo [错误] 未发现后端虚拟环境，请先进入 backend 目录并参考 README 初始化。
    pause
    exit /b
)

:: 启动后端 (新窗口)
echo [1/2] 正在启动后端服务...
start "BrushFlow Backend" cmd /k "cd backend && .venv\Scripts\python.exe -m app.main"

:: 等待服务启动
timeout /t 3 /nobreak >nul

:: 启动前端 (新窗口)
echo [2/2] 正在启动前端开发服务器...
where yarn >nul 2>nul
if %ERRORLEVEL% equ 0 (
    start "BrushFlow Frontend" cmd /k "cd frontend && yarn dev"
) else (
    start "BrushFlow Frontend" cmd /k "cd frontend && npm run dev"
)

echo.
echo ==========================================
echo 启动尝试已完成！
echo.
echo 请查看新开启的窗口以确认服务状态。
echo 默认地址:
echo   - 交互式文档: http://localhost:8000/docs
echo   - 前端界面: http://localhost:3000
echo ==========================================
echo.
echo 提示：如需停止服务，请直接关闭开启的两个命令行窗口。
pause
