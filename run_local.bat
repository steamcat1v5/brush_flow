@echo off
chcp 65001 >nul
title BrushFlow Runner

:: 解决 Windows 下 OpenSSL 链接问题 (no OPENSSL_Applink)
set SSLKEYLOGFILE=

echo ==========================================
echo     BrushFlow 一键启动脚本 (Windows)
echo ==========================================

:: 检查环境变量文件
if not exist ".env" (
    echo [信息] 未找到 .env 文件，正在从 .env.example 复制...
    copy .env.example .env >nul
)

:: 检查后端环境 (pyproject.toml)
if not exist "backend\pyproject.toml" (
    echo [错误] 未发现后端 pyproject.toml，请确保后端目录完整。
    pause
    exit /b
)

:: 启动后端 (新窗口)
echo [1/2] 正在通过 uv 启动后端服务...
start "BrushFlow Backend" cmd /k "cd backend && uv run python -m app.main"

:: 等待服务启动
timeout /t 5 /nobreak >nul

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
echo 默认地址 (请参考 .env 配置):
echo   - 后端文档: http://localhost:8765/docs
echo   - 前端界面: http://localhost:3000
echo ==========================================
echo.
echo 提示：如需停止服务，请直接关闭新开启的命令行窗口。
pause
