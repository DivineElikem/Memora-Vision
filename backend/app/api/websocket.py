"""WebSocket streaming for Memora Vision.

Provides real-time push updates to connected frontend clients for
processing status, new events, and alert hits.
"""

import json
import logging
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections and broadcasts messages to all clients."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info("WebSocket client connected (%d total)", len(self.active_connections))

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info("WebSocket client disconnected (%d total)", len(self.active_connections))

    async def broadcast(self, event_type: str, data: dict[str, Any]):
        """Broadcast a message to all connected clients."""
        message = json.dumps({"type": event_type, "data": data})
        disconnected: list[WebSocket] = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                disconnected.append(connection)
        for conn in disconnected:
            self.disconnect(conn)


# Singleton instance
ws_manager = ConnectionManager()


async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint handler."""
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep connection alive; client may send pings
            data = await websocket.receive_text()
            # Echo back as heartbeat
            if data == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)
