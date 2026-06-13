"""The simulated price engine.

The brief explicitly says we don't need real market data — we may use a random
number generator that updates prices every second. This module does exactly
that, using a *random walk* (each tick nudges the previous price by a small
random percentage) so the numbers look like a believable ticker rather than
pure noise.

It runs as a single background asyncio task for the whole server. On every tick
it updates all 5 supported stocks, then hands the fresh snapshot to a broadcast
callback (wired up in main.py) which pushes prices out over the WebSockets.
"""

from __future__ import annotations

import asyncio
import random
import time
from typing import Awaitable, Callable

from .catalogue import SUPPORTED_STOCKS, STOCK_BY_TICKER
from .config import settings


class PriceEngine:
    def __init__(self) -> None:
        # Current price per ticker, seeded from the catalogue.
        self._prices: dict[str, float] = {
            s.ticker: s.seed_price for s in SUPPORTED_STOCKS
        }
        # Previous price, so the UI can show up/down direction and % change.
        self._prev: dict[str, float] = dict(self._prices)
        self._task: asyncio.Task | None = None
        self._running = False
        # Injected by main.py at startup: async fn(snapshot) -> None
        self.broadcaster: Callable[[dict], Awaitable[None]] | None = None

    # --- Snapshot -------------------------------------------------------
    def snapshot(self) -> dict:
        """Return the current prices in a JSON-friendly shape.

        Shape:
            {
              "type": "prices",
              "ts": 1718300000.123,
              "prices": {
                 "GOOG": {"price": 175.62, "prev": 175.40, "change": 0.22,
                          "change_pct": 0.13, "direction": "up"},
                 ...
              }
            }
        """
        out = {}
        for ticker, price in self._prices.items():
            prev = self._prev[ticker]
            change = round(price - prev, 2)
            change_pct = round((change / prev) * 100, 2) if prev else 0.0
            direction = "up" if change > 0 else "down" if change < 0 else "flat"
            out[ticker] = {
                "price": round(price, 2),
                "prev": round(prev, 2),
                "change": change,
                "change_pct": change_pct,
                "direction": direction,
            }
        return {"type": "prices", "ts": time.time(), "prices": out}

    # --- The tick -------------------------------------------------------
    def _tick(self) -> None:
        """Advance every price by one realistic random step.

        Each tick combines three effects so the chart looks like a real ticker
        rather than uniform noise:

          1. **Normal move** — a Gaussian (bell-curve) percentage change scaled
             by the stock's own `volatility`. Most ticks are small; occasionally
             larger, just like real markets.
          2. **Shock** — with ~6% probability, a sudden larger jump up or down
             (a "fat tail"), which produces the visible spikes/drops.
          3. **Mean-reversion** — a gentle pull back toward the seed price so a
             long-running demo stays in a believable range instead of drifting
             to zero or the moon.
        """
        for ticker, price in self._prices.items():
            self._prev[ticker] = price
            stock = STOCK_BY_TICKER[ticker]

            # 1. Normal Gaussian move, scaled by this stock's volatility.
            move = random.gauss(0, stock.volatility)

            # 2. Occasional shock — a bigger, clearly-visible jump either way.
            if random.random() < 0.06:
                move += random.uniform(-0.05, 0.05)

            # 3. Gentle mean-reversion toward the seed price (keeps it bounded).
            reversion = (stock.seed_price - price) / stock.seed_price * 0.01

            new_price = price * (1 + move + reversion)
            # Never let a price drop below a small floor.
            self._prices[ticker] = max(round(new_price, 2), 1.0)

    # --- Lifecycle ------------------------------------------------------
    async def _run(self) -> None:
        self._running = True
        while self._running:
            self._tick()
            if self.broadcaster is not None:
                # Broadcast errors must never kill the engine loop.
                try:
                    await self.broadcaster(self.snapshot())
                except Exception as exc:  # noqa: BLE001 — defensive logging
                    print(f"[price_engine] broadcast error: {exc}")
            await asyncio.sleep(settings.PRICE_TICK_SECONDS)

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run())
            print(
                f"[price_engine] started, ticking every "
                f"{settings.PRICE_TICK_SECONDS}s"
            )

    async def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None


# A single shared engine instance for the whole application.
engine = PriceEngine()
