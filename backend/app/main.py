"""FastAPI application entrypoint.

Run with:
    uvicorn app.main:app --reload --port 8000

Responsibilities:
  * Create the FastAPI app + CORS for the React dev server.
  * Initialise the SQLite schema on startup.
  * Wire the price engine's broadcaster to the WebSocket manager and start the
    once-per-second tick loop.
  * Mount the auth, stocks and websocket routers.

Interactive API docs are served at  http://localhost:8000/docs
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import init_db
from .price_engine import engine
from .routers import auth, stocks, ws
from .ws_manager import manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- startup ---
    init_db()
    # Connect the engine to the broadcaster and start ticking.
    engine.broadcaster = manager.broadcast
    engine.start()
    print("[main] startup complete — API ready, prices ticking.")
    yield
    # --- shutdown ---
    await engine.stop()
    print("[main] shutdown complete.")


app = FastAPI(
    title="Stock Broker Client Web Dashboard API",
    description=(
        "Backend for a real-time stock dashboard: passwordless email+OTP login, "
        "per-user stock subscriptions, and a WebSocket stream of simulated "
        "prices that update once per second."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# Allow the Vite dev server (and any configured origins) to call the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router)
app.include_router(stocks.router)
app.include_router(ws.router)


@app.get("/api/health", tags=["health"])
def health() -> dict:
    """Simple liveness probe."""
    return {"status": "ok", "dev_mode": settings.DEV_MODE}
