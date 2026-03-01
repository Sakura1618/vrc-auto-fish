@echo off
chcp 65001 >nul 2>&1
title VRChat 钓鱼助手
cd /d "%~dp0"

:: ============================================
::  检查 Python
:: ============================================
python --version >nul 2>&1
if errorlevel 1 (
    echo ============================================
    echo   [错误] 未找到 Python
    echo   请安装 Python 3.10+ 并勾选 "Add to PATH"
    echo   下载: https://www.python.org/downloads/
    echo ============================================
    pause
    exit /b 1
)

:: ============================================
::  检查依赖是否已安装
:: ============================================
python -c "import cv2, keyboard, torch, ultralytics" 2>nul
if errorlevel 1 (
    echo ============================================
    echo   首次运行，正在安装依赖...
    echo   (仅需一次，请耐心等待)
    echo ============================================
    echo.
    call :install_deps
    if errorlevel 1 (
        echo [错误] 安装失败，请检查网络连接后重试
        pause
        exit /b 1
    )
    echo.
    echo ============================================
    echo   依赖安装完成！正在启动...
    echo ============================================
    echo.
)

:: ============================================
::  启动程序
:: ============================================
python main.py
if errorlevel 1 pause
exit /b 0

:: ============================================
::  安装依赖子过程
:: ============================================
:install_deps
echo.
echo [1/2] 安装 PyTorch...
call :install_torch

echo.
echo [2/2] 安装其他依赖...
pip install -r requirements.txt
if errorlevel 1 exit /b 1
exit /b 0

:install_torch
nvidia-smi >nul 2>&1
if errorlevel 1 (
    echo   未检测到 NVIDIA GPU，安装 CPU 版 PyTorch
    pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
) else (
    echo   检测到 NVIDIA GPU，安装 CUDA 版 PyTorch (GPU 加速)
    pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
)
exit /b 0