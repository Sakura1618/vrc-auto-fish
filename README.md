# VRChat 自动钓鱼助手 (FISH!)

VRChat 世界 **FISH!** 的自动钓鱼脚本。支持 YOLO 目标检测 + PD 控制器，全自动抛竿、提竿、小游戏操控。

## 功能

- **自动抛竿 / 提竿** — 检测咬钩动画，自动完成钓鱼流程
- **小游戏自动控制** — PD 控制器追踪鱼的位置，自动操控白条
- **YOLO 目标检测** — 训练后可替代模板匹配，准确率更高
- **GUI 界面** — 参数可视化调节，实时调试窗口
- **热键控制** — F9 开始/暂停，F10 停止，F11 调试模式
- **VRChat OSC 输入** — 可选 OSC 输入方式，不占用鼠标

## 快速开始

### 方式一：源码运行 (推荐)

1. 安装 [Python 3.10+](https://www.python.org/downloads/)（安装时勾选 **Add to PATH**）
2. 双击 `install.bat` 一键安装依赖（自动检测 GPU，安装对应版本 PyTorch）
3. 双击 `start.bat` 启动程序

### 方式二：手动安装

```bash
# 安装 PyTorch (GPU 版)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128

# 或 CPU 版
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu

# 安装其他依赖
pip install -r requirements.txt

# 启动
python main.py
```

## 使用说明

1. 先启动 VRChat 并进入 FISH! 世界
2. 运行程序，点击「选择窗口」绑定 VRChat 窗口
3. 点击「框选区域」选择钓鱼小游戏的检测范围（可选）
4. 按 **F9** 开始自动钓鱼

## 快捷键

| 按键 | 功能 |
|------|------|
| F9   | 开始 / 暂停 |
| F10  | 停止 |
| F11  | 调试模式 (显示检测窗口) |

## 项目结构

```
├── main.py          # 入口
├── config.py        # 全局配置
├── core/            # 核心逻辑
│   ├── bot.py       # 钓鱼主循环 + PD控制器
│   ├── detector.py  # 模板匹配检测
│   ├── yolo_detector.py  # YOLO 检测
│   ├── screen.py    # 截屏
│   ├── window.py    # 窗口管理
│   └── input_ctrl.py     # 输入控制
├── gui/             # GUI 界面
│   └── app.py
├── utils/           # 工具
│   └── logger.py
├── img/             # 模板图片
├── yolo/            # YOLO 模型 & 训练工具
├── install.bat      # 一键安装
└── start.bat        # 一键启动
```

## 更新补丁

如果使用 EXE 版本，下载补丁 zip 后解压到 EXE 同级目录，确保生成 `patch/` 文件夹即可。程序启动时会自动加载补丁。

## License

MIT
