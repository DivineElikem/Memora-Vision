"""Memora Vision — FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import create_router
from app.api.websocket import websocket_endpoint
from app.core.config import get_settings
from app.storage.database import Database
from app.services.repository import Repository


def create_app() -> FastAPI:
    settings = get_settings()
    db = Database(settings.database_path)
    repo = Repository(db)

    app = FastAPI(title="Memora Vision API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Serve uploaded videos
    app.mount("/media", StaticFiles(directory=settings.upload_dir), name="media")

    # Serve keyframe thumbnails
    settings.keyframe_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/thumbnails", StaticFiles(directory=settings.keyframe_dir), name="thumbnails")

    # WebSocket endpoint for real-time streaming
    app.add_api_websocket_route("/ws", websocket_endpoint)

    app.include_router(create_router(settings, repo))
    return app


app = create_app()
