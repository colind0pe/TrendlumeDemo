# 🎬 Trendlume —— AI 全自动短视频引擎

<p align="center"><a href="README_EN.md">English</a> | <b>中文</b></p>

Trendlume 是一个基于 AI 的全自动短视频创作与生成引擎。只需输入主题或旁白文本，即可一键自动化完成视频脚本生成、配图与动态视频生成、语音合成、背景音乐混合及最终视频渲染。

---

## ✨ 功能亮点

- 💡 **AI 智能文案**：输入主题或话题，大语言模型自动生成结构化分镜脚本与解说词。
- 🎨 **多模态画面生成**：
  - **ComfyUI 工作流集成**：支持本地 ComfyUI 及 RunningHub 云端工作流（FLUX、SDXL、WAN 2.1 等）。
  - **直连 API 服务**：支持 DashScope（通义万相）、OpenAI (DALL-E 3)、Seedream、Seedance、快手可灵 (Kling) 等直接生成图像与视频。
- 🎤 **多通道语音合成**：内置 Edge-TTS，并支持基于 ComfyUI 的自定义 TTS 引擎与多语言音色。
- 📐 **精美 HTML 帧渲染模版**：支持竖屏 (1080x1920)、横屏 (1920x1080) 等多样化美学排版与动画模版。
- 🎵 **背景音乐与音画对齐**：自动匹配 BGM 音量与时长，保证音画完美同步。
- 🚀 **双模式运行**：支持交互式 **Streamlit Web UI** 与生产级 **FastAPI 接口服务**。

---

## 🛠️ 快速上手

### 环境要求
- **Python**: >= 3.11
- **包管理器**: [uv](https://docs.astral.sh/uv/) (推荐)
- **多媒体工具**: 系统需安装 [FFmpeg](https://ffmpeg.org/) 并加入环境变量 PATH
- **浏览器内核**: 支持 Playwright Chromium (用于 HTML 模版渲染截图)

### 1. 克隆与安装依赖

```bash
# 1. 安装依赖并创建虚拟环境
uv sync

# 2. 安装 Playwright 浏览器依赖 (用于模版渲染)
uv run playwright install --with-deps chromium
```

### 2. 配置文件设置

复制配置模版文件：

```bash
cp config.example.yaml config.yaml
```

编辑 `config.yaml` 填写您的模型配置：
- `llm`: 配置 OpenAI / DeepSeek / 阿里云 DashScope 等兼容 OpenAI 格式的 API Key 和 Base URL。
- `comfyui`: 配置本地 ComfyUI 地址 (`http://127.0.0.1:8188`) 或 RunningHub API Key。
- `api_providers` (可选): 直接调用 DashScope / Kling 等第三方 API 生成图像与视频。

### 3. 启动应用

#### 启动 Web 界面
Windows 用户直接双击 `start_web.bat`，或在终端运行：
```bash
uv run streamlit run web/app.py
```
浏览器打开: `http://localhost:8501`

#### 启动 API 服务
```bash
uv run python api/app.py --host 0.0.0.0 --port 8000
```
API 文档地址: `http://localhost:8000/docs`

---

## 🐳 Docker 部署

使用 Docker Compose 一键启动：

```bash
# 启动所有服务 (API + Web UI)
docker-compose up -d
```

- Web UI: `http://localhost:8501`
- API 服务: `http://localhost:8000`

---

## 📁 目录结构

```text
Trendlume/
├── api/                  # FastAPI 后端服务与路由定义
├── bgm/                  # 默认背景音乐
├── docs/                 # 帮助文档 (FAQ) 与模版预览图
│   ├── images/           # 模版选择预览缩略图
│   └── FAQ_CN.md         # 常见问题
├── resources/            # 应用基础静态资源
├── templates/            # HTML 分镜渲染模版
│   ├── 1080x1920/        # 竖屏模版
│   └── 1920x1080/        # 横屏模版
├── trendlume/            # Python 核心业务逻辑与服务层
│   ├── config/           # 配置管理与 Schema
│   ├── models/           # 数据模型定义
│   ├── pipelines/        # 视频生成流水线
│   ├── prompts/          # 提示词模版
│   ├── services/         # LLM, TTS, Media, Frame 渲染与合成服务
│   └── utils/            # 实用工具函数
├── web/                  # Streamlit 前端交互界面与组件
├── workflows/            # ComfyUI 工作流模版定义
├── config.example.yaml   # 配置文件模版
├── docker-compose.yml    # Docker Compose 编排
├── Dockerfile            # Docker 构建文件
└── pyproject.toml        # 项目依赖与元数据
```

---

## 📄 开源许可证

本项目基于 [Apache-2.0](LICENSE) 许可证开源。
