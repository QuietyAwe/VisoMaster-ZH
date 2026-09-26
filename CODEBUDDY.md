# CODEBUDDY.md

本文件用于指导 CodeBuddy（codebuddy.ai）在本仓库中开展工作。

## 项目概述

VisoMaster-ZH 是 VisoMaster 的中文汉化版本，是一个面向图片与视频的换脸与编辑工具。它使用 AI 模型（InsightFace、LivePortrait 等）完成人脸检测、换脸与画质增强，并支持 TensorRT/CUDA 加速。

## 常用命令

### 启动应用
```bash
# 标准启动（激活 conda 环境、转换 UI、运行程序）
Start.bat

# 或手动启动：
conda activate visomaster
python main.py
```

### UI 文件转换
**重要**：界面定义在 `app/ui/core/MainWindow.ui`（Qt Designer XML 格式），启动脚本会自动由它生成 `app/ui/core/main_window.py`。

```bash
# 如需手动转换
pyside6-uic app/ui/core/MainWindow.ui -o app/ui/core/main_window.py
```

**禁止直接编辑 `main_window.py`** —— 它会在启动时被覆盖。请始终修改 `MainWindow.ui`。

### 安装依赖
```bash
# CUDA 12.4
pip install -r requirements_cu124.txt

# CUDA 11.8
pip install -r requirements_cu118.txt
```

## 架构说明

### 核心组成

**入口**：`main.py` → `app/ui/main_ui.py:MainWindow`

**UI 层**（`app/ui/`）：
- `main_ui.py` —— 主窗口类，负责信号/槽连接与控件初始化
- `core/MainWindow.ui` —— Qt Designer 界面定义文件（改这个文件，不要改 main_window.py）
- `core/main_window.py` —— 自动生成的 UI 代码（禁止编辑）
- `widgets/` —— 自定义控件、布局与界面逻辑
  - `*_layout_data.py` —— 界面布局定义（标签、选项、提示文本）
  - `widget_components.py` —— 自定义控件类（CardButton、ToggleButton 等）
  - `actions/` —— 界面动作处理（按钮点击、参数变更）

**处理层**（`app/processors/`）：
- `models_processor.py` —— 中心模型管理器（加载/运行所有 AI 模型）
- `video_processor.py` —— 视频播放、取帧、录制
- `workers/frame_worker.py` —— 逐帧处理线程（人脸检测、换脸）
- `face_detectors.py` —— 人脸检测模型（RetinaFace、YOLO、SCRFD 等）
- `face_swappers.py` —— 换脸模型（Inswapper、SimSwap、GhostFace、DFM）
- `face_landmark_detectors.py` —— 用于人脸对齐的关键点检测
- `face_masks.py` —— 遮罩处理（遮挡、XSeg、文本遮罩）
- `face_restorers.py` —— 人脸修复/超分
- `frame_enhancers.py` —— 画面增强（上色、超分）

**辅助模块**（`app/helpers/`）：
- `miscellaneous.py` —— 通用工具函数、DFM 模型处理
- `typing_helper.py` —— 参数与布局的类型定义

### 关键设计模式

**参数系统**：
- 界面参数定义在 `*_layout_data.py` 的字典中
- 每个人脸的参数存放在 `main_window.parameters[face_id]`
- 全局控制项存放在 `main_window.control`
- `ParametersDict` 提供默认值回退机制

**模型加载**：
- 模型定义在 `app/processors/models_data.py`
- 通过 `models_processor.load_model()` 惰性加载
- 支持 ONNX、TensorRT、PyTorch 后端

**逐帧处理管线**（位于 `frame_worker.py`）：
1. 取帧 → 2. 人脸检测 → 3. 人脸匹配 → 4. 换脸 → 5. 画质增强 → 6. 输出

### 界面布局文件

- `common_layout_data.py` —— 通用控件（人脸修复、颜色迁移）
- `swapper_layout_data.py` —— 换脸参数（模型、遮罩、融合）
- `settings_layout_data.py` —— 全局设置（检测器、推理后端、摄像头）
- `face_editor_layout_data.py` —— LivePortrait 人脸编辑控件

## 开发注意事项

- **Python 版本**：需 3.10+（代码使用了 `match` 语句）
- **Conda 环境**：`visomaster`
- **TensorRT**：本地副本位于 `TensorRT-10.13.0.35/`（不纳入 git）
- **模型**：首次使用时下载到 `model_assets/`
- **工作区**：设置保存在 `last_workspace.json`

## Git 与上游仓库

- **Origin**：`wwzhifeng/VisoMaster-ZH`（中文汉化分支）
- **Upstream**：`visomaster/VisoMaster`（原始英文版本）
- **同步命令**：`git fetch upstream && git merge upstream/main`

与上游同步时，`*_layout_data.py` 与 `main_window.py` 中的中文翻译可能需要手动合并。

## CodeBuddy 协作约定

- 交流使用简体中文；新增界面文案默认中文，并与现有 `*_layout_data.py` 的翻译风格保持一致。
- 修改界面时只改 `app/ui/core/MainWindow.ui`，不要改 `app/ui/core/main_window.py`；需要重建时使用上面的 `pyside6-uic` 命令。
- 未经验证不要改动 `app/processors/` 下的模型加载与推理管线；涉及 TensorRT / CUDA 的改动需说明影响面。
- 不要提交大体积二进制模型、`model_assets/` 与 `TensorRT-10.13.0.35/`。
- 优先使用定向检索与小范围编辑，避免大规模重写用户文件。
