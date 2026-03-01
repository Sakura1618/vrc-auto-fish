@echo off
chcp 65001 >nul 2>&1
title VRChat 钓鱼助手
cd /d "%~dp0"

:: 快速检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先运行 install.bat
    pause
    exit /b 1
)

:: 快速检查核心依赖
python -c "import cv2, keyboard, torch, ultralytics" 2>nul
if errorlevel 1 (
    echo [提示] 依赖未安装，请先运行 install.bat
    pause
    exit /b 1
)

python main.py
if errorlevel 1 pause
