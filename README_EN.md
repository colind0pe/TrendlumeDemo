# 🎬 Trendlume —— AI Auto Short Video Engine

<p align="center"><b>English</b> | <a href="README.md">中文</a></p>

Trendlume is an AI-powered automated short video creation and generation engine. Simply input a topic or narration text, and it automatically handles video script generation, image/video asset generation, voice synthesis, background music mixing, and final video rendering.

---

## ✨ Features

- 💡 **AI Script Generation**: Powered by LLMs to automatically generate storyboard scripts and narrations based on any topic.
- 🎨 **Multimodal Visuals**:
  - **ComfyUI Integration**: Supports local ComfyUI and RunningHub cloud workflows (FLUX, SDXL, WAN 2.1, etc.).
  - **Direct API Providers**: Supports DashScope, OpenAI (DALL-E 3), Seedream, Seedance, Kling, etc., for direct media generation.
- 🎤 **Versatile Voice Synthesis**: Built-in Edge-TTS, and supports ComfyUI-based custom TTS models and multilingual voices.
- 📐 **HTML Frame Templates**: Aesthetic vertical (1080x1920) and horizontal (1920x1080) layout and animation templates.
- 🎵 **BGM & Audio-Visual Alignment**: Automatic BGM volume balancing and precise audio-visual synchronization.
- 🚀 **Dual Interfaces**: Interactive **Streamlit Web UI** and production-ready **FastAPI Backend**.

---

## 🛠️ Quick Start

### Requirements
- **Python**: >= 3.11
- **Package Manager**: [uv](https://docs.astral.sh/uv/) (Recommended)
- **Multimedia**: [FFmpeg](https://ffmpeg.org/) installed and available in PATH
- **Browser Runtime**: Playwright Chromium (for HTML template rendering)

### 1. Installation

```bash
# 1. Install dependencies & create virtual environment
uv sync

# 2. Install Playwright browser dependencies
uv run playwright install --with-deps chromium
```

### 2. Configuration

Copy the example configuration:

```bash
cp config.example.yaml config.yaml
```

Edit `config.yaml` with your API credentials:
- `llm`: OpenAI-compatible API credentials (OpenAI, DeepSeek, Qwen, etc.).
- `comfyui`: Local ComfyUI URL (`http://127.0.0.1:8188`) or RunningHub API Key.
- `api_providers` (optional): Third-party API keys for DashScope, Kling, etc.

### 3. Launching

#### Web UI
Run `start_web.bat` (Windows) or in your terminal:
```bash
uv run streamlit run web/app.py
```
Open browser at: `http://localhost:8501`

#### API Server
```bash
uv run python api/app.py --host 0.0.0.0 --port 8000
```
API Documentation: `http://localhost:8000/docs`

---

## 🐳 Docker Deployment

Run with Docker Compose:

```bash
docker-compose up -d
```

- Web UI: `http://localhost:8501`
- API Service: `http://localhost:8000`

---

## 📁 Directory Structure

```text
Trendlume/
├── api/                  # FastAPI routes and schemas
├── bgm/                  # Default background music
├── docs/                 # FAQ and template previews
│   ├── images/           # Template preview thumbnails
│   └── FAQ.md            # Frequently asked questions
├── resources/            # Application static assets
├── templates/            # HTML storyboard templates
├── trendlume/            # Python core engine & services
│   ├── config/           # Configuration management
│   ├── models/           # Data models
│   ├── pipelines/        # Video generation pipelines
│   ├── prompts/          # Prompt templates
│   ├── services/         # LLM, TTS, Media, and Video rendering
│   └── utils/            # Helper utilities
├── web/                  # Streamlit UI application
├── workflows/            # ComfyUI workflows
├── config.example.yaml   # Configuration template
├── docker-compose.yml    # Docker Compose setup
├── Dockerfile            # Dockerfile
└── pyproject.toml        # Project dependencies and metadata
```

---

## 📄 License

This project is licensed under the [Apache-2.0](LICENSE) license.
