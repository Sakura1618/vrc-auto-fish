@echo off
chcp 65001 >nul 2>&1
title VRChat 钓鱼助手 - 安装依赖

echo ============================================
echo   VRChat 钓鱼助手 - 一键安装
echo ============================================
echo.

:: 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.10+ 并勾选 "Add to PATH"
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/3] 检测到 Python:
python --version
echo.

:: 检查是否已安装 PyTorch
echo [2/3] 检测 GPU...
python -c "import torch; print(f'  PyTorch {torch.__version__}  CUDA: {torch.cuda.is_available()}')" 2>nul
if errorlevel 1 (
    echo   未安装 PyTorch，将自动安装...
    call :install_torch
) else (
    echo   PyTorch 已安装
)

echo.
echo [3/3] 安装其他依赖...
pip install -r requirements.txt
echo.

echo ============================================
echo   安装完成! 双击 启动.bat 启动程序
echo ============================================
pause
exit /b 0

:install_torch
echo.
echo 检测 NVIDIA GPU 是否支持 CUDA...
nvidia-smi >nul 2>&1
if errorlevel 1 (
    echo   未检测到 NVIDIA GPU，安装 CPU 版 PyTorch
    pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
) else (
    echo   检测到 NVIDIA GPU，安装 CUDA 版 PyTorch (GPU 加速)
    pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
)
exit /b 0