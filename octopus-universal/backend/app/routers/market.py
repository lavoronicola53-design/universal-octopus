"""
routers/market.py

Endpoint per: elenco mercati/timeframe supportati e recupero dati OHLCV
storici (necessari al frontend per disegnare il grafico su cui il trader
selezionera' manualmente il frattale).
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..schemas import MarketListResponse, OHLCVResponse, OHLCVBar
from ..services.data_provider import get_provider, SUPPORTED_MARKETS, TIMEFRAME_SECONDS

router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("/list", response_model=MarketListResponse)
def list_markets() -> MarketListResponse:
    return MarketListResponse(markets=SUPPORTED_MARKETS, timeframes=list(TIMEFRAME_SECONDS.keys()))


@router.get("/ohlcv", response_model=OHLCVResponse)
def get_ohlcv(
    market: str = Query(..., description="Es. BTC/USDT"),
    timeframe: str = Query(..., description="Es. 15m"),
    start_timestamp: float = Query(..., description="Epoch seconds inizio range"),
    end_timestamp: float = Query(..., description="Epoch seconds fine range"),
) -> OHLCVResponse:
    if market not in SUPPORTED_MARKETS:
        raise HTTPException(400, f"Mercato non supportato: {market}")
    if timeframe not in TIMEFRAME_SECONDS:
        raise HTTPException(400, f"Timeframe non supportato: {timeframe}")
    if end_timestamp <= start_timestamp:
        raise HTTPException(400, "end_timestamp deve essere successivo a start_timestamp")

    provider = get_provider()
    try:
        series = provider.get_ohlcv(market, timeframe, start_timestamp, end_timestamp)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    bars = [OHLCVBar(**rec) for rec in series.to_records()]
    return OHLCVResponse(market=market, timeframe=timeframe, bars=bars)
