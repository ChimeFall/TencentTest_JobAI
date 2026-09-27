@echo off
echo ========================================
echo   Offer捕手 - AI求职匹配系统
echo ========================================
echo.

REM Start Backend
echo [1/2] 启动后端服务...
start "Offer捕手-后端" cmd /c "cd /d %~dp0backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"

REM Wait a bit for backend
timeout /t 3 /nobreak >nul

REM Start Frontend
echo [2/2] 启动前端开发服务器...
start "Offer捕手-前端" cmd /c "cd /d %~dp0frontend && npm run dev"

echo.
echo ========================================
echo 后端API: http://localhost:8000
echo 前端页面: http://localhost:5173
echo API文档: http://localhost:8000/docs
echo ========================================
echo.
echo 按任意键退出...
pause >nul
