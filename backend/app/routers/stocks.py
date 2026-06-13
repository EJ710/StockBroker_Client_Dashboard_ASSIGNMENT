"""Stock catalogue + per-user subscription routes.

    GET    /api/stocks/supported              -> the 5 supported stocks
    GET    /api/stocks/subscriptions          -> my watchlist
    POST   /api/stocks/subscriptions { ticker}-> add a ticker to my watchlist
    DELETE /api/stocks/subscriptions/{ticker} -> remove a ticker

Every write also pushes the updated ticker set into the WebSocket manager so
the user's open dashboards immediately start/stop receiving that stock.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from .. import database as db
from ..catalogue import SUPPORTED_STOCKS, is_supported
from ..deps import get_current_user
from ..schemas import (
    SubscribeIn,
    SubscriptionsOut,
    SupportedStockOut,
)
from ..ws_manager import manager

router = APIRouter(prefix="/api/stocks", tags=["stocks"])


@router.get("/supported", response_model=list[SupportedStockOut])
def supported() -> list[SupportedStockOut]:
    """The fixed catalogue of tickers a user is allowed to subscribe to."""
    return [SupportedStockOut(ticker=s.ticker, name=s.name) for s in SUPPORTED_STOCKS]


@router.get("/subscriptions", response_model=SubscriptionsOut)
def my_subscriptions(user: dict = Depends(get_current_user)) -> SubscriptionsOut:
    return SubscriptionsOut(tickers=db.list_subscriptions(user["id"]))


@router.post(
    "/subscriptions",
    response_model=SubscriptionsOut,
    status_code=status.HTTP_201_CREATED,
)
async def subscribe(
    body: SubscribeIn, user: dict = Depends(get_current_user)
) -> SubscriptionsOut:
    ticker = body.ticker.strip().upper()
    if not is_supported(ticker):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"'{ticker}' is not a supported ticker.",
        )
    db.add_subscription(user["id"], ticker)  # idempotent (UNIQUE constraint)
    tickers = db.list_subscriptions(user["id"])
    # Keep any open WebSocket(s) for this user in sync immediately.
    await manager.update_user_tickers(user["id"], set(tickers))
    return SubscriptionsOut(tickers=tickers)


@router.delete("/subscriptions/{ticker}", response_model=SubscriptionsOut)
async def unsubscribe(
    ticker: str, user: dict = Depends(get_current_user)
) -> SubscriptionsOut:
    db.remove_subscription(user["id"], ticker.strip().upper())
    tickers = db.list_subscriptions(user["id"])
    await manager.update_user_tickers(user["id"], set(tickers))
    return SubscriptionsOut(tickers=tickers)
