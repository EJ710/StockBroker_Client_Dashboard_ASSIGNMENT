"""The live-price WebSocket endpoint.

    WS /ws/prices?token=<JWT>

The browser opens this socket after login. We authenticate using the JWT
passed as a query parameter (browsers can't set Authorization headers on a
WebSocket handshake), load the user's current subscriptions, register the
connection with the manager, then simply wait. The price engine's broadcast
loop does the pushing — once per second, each socket receives only its user's
subscribed prices, fulfilling requirements #2 (no refresh) and #3 (async,
per-user, multi-client).
"""

from __future__ import annotations

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from .. import database as db
from ..price_engine import engine
from ..security import decode_access_token
from ..ws_manager import manager

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/prices")
async def prices_ws(websocket: WebSocket, token: str = Query(default="")) -> None:
    # --- Authenticate the handshake ---
    payload = decode_access_token(token)
    if payload is None:
        # 1008 = policy violation; close before accepting.
        await websocket.close(code=1008)
        return
    user = db.get_user_by_email(payload.get("email", ""))
    if user is None:
        await websocket.close(code=1008)
        return

    # --- Register the connection with the user's current watchlist ---
    tickers = set(db.list_subscriptions(user["id"]))
    conn = await manager.connect(websocket, user["id"], tickers)

    # Send an immediate snapshot so the UI paints prices without waiting a tick.
    initial = engine.snapshot()
    initial_prices = {t: initial["prices"][t] for t in tickers if t in initial["prices"]}
    await websocket.send_json(
        {"type": "prices", "ts": initial["ts"], "prices": initial_prices}
    )

    # --- Keep the socket open ---
    # We don't require any client messages, but we read in a loop so we notice
    # disconnects promptly. A client MAY send {"type":"ping"} to keep-alive.
    try:
        while True:
            await websocket.receive_text()  # raises WebSocketDisconnect on close
    except WebSocketDisconnect:
        await manager.disconnect(conn)
    except Exception:  # noqa: BLE001 — any error ends the connection cleanly
        await manager.disconnect(conn)
