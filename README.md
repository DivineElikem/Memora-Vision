# Memora Vision

**AI-Powered Visual Memory Assistant**

Memora Vision transforms camera feeds into searchable, conversational intelligence. Instead of manually reviewing footage, interact with your visual memory using natural language.

## What It Does

- **Scene Understanding** — Rich VLM-powered captions describing actions, appearances, and spatial relationships
- **Conversational Memory** — Multi-turn chat: "Where did I leave my bag?", "Who entered today?", "Summarize the morning"
- **Intelligent Alerts** — Natural language rules like "notify me when something unusual happens" with LLM-based semantic evaluation
- **Real-Time Streaming** — WebSocket push updates as events are detected
- **Voice Interaction** — Speak questions and hear answers via browser speech APIs

## Architecture

- **Backend**: FastAPI + SQLite + OpenCV + Qwen2.5-VL (on AMD MI300X via ROCm)
- **Frontend**: React + Vite + TypeScript + Vanilla CSS
- **AI Pipeline**: YOLO object detection → VLM scene captioning → LLM query answering
- **Voice**: Web Speech API (input) + Speech Synthesis (output)

## Quick Start

### 1. Backend

```bash
cd backend
cp .env.example .env    # Configure model URLs
uv run uvicorn app.main:app --reload
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

### 3. AMD GPU Server (Optional)

See [AMD_CLOUD_GUIDE.md](AMD_CLOUD_GUIDE.md) for deploying Qwen2.5-VL on MI300X.

## How It Works

1. **Upload** an MP4 video
2. **Watch** as Memora analyzes every frame — detecting objects, understanding scenes, and building structured memories
3. **Ask** natural language questions: *"What happened while I was away?"*
4. **Set alerts**: *"Notify me when someone acts suspiciously"*
5. **Review** the activity timeline with rich captions and frame thumbnails

## Repo Layout

```
backend/          FastAPI + SQLite + processing pipeline
  app/
    api/          REST endpoints + WebSocket
    core/         Configuration
    models/       Pydantic schemas
    services/     Detection, captioning, query engine, alerts, summarizer
    storage/      Database layer
frontend/         React + Vite UI
  src/
    api/          API client + WebSocket
    hooks/        Speech recognition
mobile/           Flutter companion (future)
```

## Tech Stack

| Component | Technology |
|---|---|
| Backend | FastAPI, SQLite, OpenCV |
| Frontend | React 19, Vite 5, TypeScript |
| Object Detection | YOLOv8 (ultralytics) |
| Scene Understanding | Qwen2.5-VL-7B (vLLM on AMD MI300X) |
| Query Answering | Qwen2.5-VL-7B (same model) |
| Voice | Web Speech API + Speech Synthesis |
| GPU Acceleration | AMD Instinct MI300X, ROCm, vLLM |
