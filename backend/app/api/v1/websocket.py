"""Real-Time WebSocket Progress and Telemetry Broadcast Subsystem."""

from __future__ import annotations

import asyncio
from typing import Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.app.core.gpu_monitor import GPUMonitor
from backend.app.core.logger import get_logger
from backend.app.schemas.job import JobProgressUpdate

logger = get_logger(__name__, subsystem="WEBSOCKET")

router = APIRouter()


class WebSocketManager:
    """Maintains active WebSocket connections and broadcasts real-time telemetry."""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info("Client connected. Total active WebSocket connections: %d", len(self.active_connections))

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        logger.info("Client disconnected. Total active WebSocket connections: %d", len(self.active_connections))

    async def broadcast_progress(self, update: JobProgressUpdate):
        """Broadcast progress update to all connected frontends."""
        if not self.active_connections:
            return

        payload = update.model_dump_json()
        dead_connections = set()
        for conn in self.active_connections:
            try:
                await conn.send_text(payload)
            except Exception:
                dead_connections.add(conn)

        for dead in dead_connections:
            self.active_connections.discard(dead)

    async def broadcast_json(self, data: dict):
        """Broadcast arbitrary JSON object to all clients."""
        if not self.active_connections:
            return
        dead = set()
        for conn in self.active_connections:
            try:
                await conn.send_json(data)
            except Exception:
                dead.add(conn)
        for d in dead:
            self.active_connections.discard(d)


ws_manager = WebSocketManager()


@router.websocket("/ws/pipeline-progress")
async def websocket_pipeline_progress(websocket: WebSocket):
    """Real-time pipeline progress and hardware metrics endpoint."""
    await ws_manager.connect(websocket)
    try:
        # Initial greeting with live hardware metrics
        metrics = GPUMonitor.query_metrics()
        await websocket.send_json({
            "type": "HARDWARE_STATUS",
            "metrics": metrics.model_dump(),
        })

        while True:
            # Keep-alive receive
            data = await websocket.receive_text()
            if data == "ping":
                metrics = GPUMonitor.query_metrics()
                await websocket.send_json({
                    "type": "PONG",
                    "metrics": metrics.model_dump(),
                })
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.debug("WebSocket error: %s", str(e))
        ws_manager.disconnect(websocket)
