"""WebSocket connection manager — the multi-user, asynchronous fan-out.

This is what makes requirement #3 work: two (or more) users, each watching a
*different* set of stocks, both get live updates at the same time without
interfering with each other.

How it works:
  * Each open WebSocket is tracked in a `Connection` holding the user's id and
    the set of tickers that user currently subscribes to.
  * On every price tick the engine calls `broadcast(snapshot)`. For each
    connection we filter the snapshot down to *that user's* tickers and send
    only those — so User A never receives User B's stocks.
  * When a user subscribes/unsubscribes via the REST API, the route calls
    `update_user_tickers()` so every one of that user's open tabs immediately
    reflects the change on the next tick.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from fastapi import WebSocket


@dataclass
class Connection:
    websocket: WebSocket
    user_id: int
    tickers: set[str] = field(default_factory=set)


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: list[Connection] = []
        # Guards mutation of the connection list across concurrent tasks.
        self._lock = asyncio.Lock()

    async def connect(
        self, websocket: WebSocket, user_id: int, tickers: set[str]
    ) -> Connection:
        await websocket.accept()
        conn = Connection(websocket=websocket, user_id=user_id, tickers=set(tickers))
        async with self._lock:
            self._connections.append(conn)
        print(f"[ws] user {user_id} connected ({len(self._connections)} open)")
        return conn

    async def disconnect(self, conn: Connection) -> None:
        async with self._lock:
            if conn in self._connections:
                self._connections.remove(conn)
        print(f"[ws] user {conn.user_id} disconnected "
              f"({len(self._connections)} open)")

    async def update_user_tickers(self, user_id: int, tickers: set[str]) -> None:
        """Update the watched tickers for every open connection of a user."""
        async with self._lock:
            for conn in self._connections:
                if conn.user_id == user_id:
                    conn.tickers = set(tickers)

    async def broadcast(self, snapshot: dict) -> None:
        """Push each connection the slice of prices it subscribes to."""
        all_prices: dict = snapshot.get("prices", {})

        # Copy the list under the lock so we can send without holding it.
        async with self._lock:
            connections = list(self._connections)

        dead: list[Connection] = []
        for conn in connections:
            # Filter the global snapshot down to this user's tickers.
            filtered = {
                t: all_prices[t] for t in conn.tickers if t in all_prices
            }
            payload = {
                "type": "prices",
                "ts": snapshot.get("ts"),
                "prices": filtered,
            }
            try:
                await conn.websocket.send_json(payload)
            except Exception:  # noqa: BLE001 — connection went away mid-send
                dead.append(conn)

        # Reap any connections that failed to receive.
        if dead:
            async with self._lock:
                for conn in dead:
                    if conn in self._connections:
                        self._connections.remove(conn)


# A single shared manager instance for the whole application.
manager = ConnectionManager()
