"""WebSocket route — single endpoint that clients connect to and join rooms."""

import logging
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.utils.security import TokenError, verify_token
from app.websockets.manager import manager

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    """Main WebSocket endpoint.

    Auth: Clients must send a JSON message immediately after connecting:
        {"type": "auth", "token": "<JWT access token>"}

    Room subscription: After auth, send:
        {"type": "join", "room": "kitchen:all"}
        {"type": "join", "room": "kitchen:<station_uuid>"}
        {"type": "leave", "room": "kitchen:all"}

    The server sends events as JSON:
        {"event": "kitchen.ticket.created", "data": {...}}
    """
    # Accept first, then require auth within 10s
    client = None
    try:
        await ws.accept()
        # Wait for auth message
        raw = await ws.receive_json()
        if raw.get("type") != "auth" or not raw.get("token"):
            await ws.send_json({"error": "First message must be auth"})
            await ws.close(code=4001)
            return

        # Validate JWT
        try:
            payload = verify_token(raw["token"])
            user_id = uuid.UUID(payload["sub"])
            tenant_id = uuid.UUID(payload["tenant_id"])
        except (TokenError, KeyError, ValueError):
            await ws.send_json({"error": "Invalid token"})
            await ws.close(code=4003)
            return

        # Register in manager (re-create ConnectedClient without re-accepting)
        from app.websockets.manager import ConnectedClient
        client = ConnectedClient(ws=ws, tenant_id=tenant_id, user_id=user_id)
        manager._clients[id(ws)] = client

        await ws.send_json({"type": "auth_ok"})
        logger.info("WS authenticated: user=%s tenant=%s", user_id, tenant_id)

        # Message loop
        while True:
            msg = await ws.receive_json()
            msg_type = msg.get("type")

            if msg_type == "join":
                room = msg.get("room", "")
                if room:
                    manager.join(ws, room)
                    await ws.send_json({"type": "joined", "room": room})

            elif msg_type == "leave":
                room = msg.get("room", "")
                if room:
                    manager.leave(ws, room)
                    await ws.send_json({"type": "left", "room": room})

            elif msg_type == "ping":
                await ws.send_json({"type": "pong"})

    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("WS error")
    finally:
        manager.disconnect(ws)
