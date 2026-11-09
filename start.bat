@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ========================================================
echo   NIKKE 立绘壁纸工坊 - 源码开发版启动器
echo ========================================================
echo 正在启动开发栈 (后端 8766 + 前端 Vite 5173 + 桌面窗口)...
python scripts\start_dev.py
if errorlevel 1 (
    echo.
    echo 启动异常，请检查开发环境。
    pause
)
