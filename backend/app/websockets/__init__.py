"""WebSocket infrastructure — connection manager and room-based broadcasting."""

from app.websockets.manager import ConnectionManager, manager

__all__ = ["ConnectionManager", "manager"]
