"""
yahoo_provider.py

Provider di dati di mercato REALI (non sintetici) basato su Yahoo Finance.
Gratuito e senza API key. Copre i tre asset richiesti con dati veri:

    BTC/USDT  -> BTC-USD
    XAU/USD   -> GC=F   (Gold Futures COMEX)  [fallback: XAUUSD=X]
    XAG/USD   -> SI=F   (Silver Futures COMEX) [fallback: XAGUSD=X]
    ETH/USDT  -> ETH-USD
    EUR/USD   -> EURUSD=X
    GBP/USD   -> GBPUSD=X
    NAS100    -> ^NDX
    SPX500    -> ^GSPC

Yahoo Finance limita la profondità storica in base all'intervallo:
  - intraday fino a 1m: ultimi ~7-30 giorni
  - 1h: ultimi ~730 giorni
  - 1d/1wk: molti anni

NOTA: Yahoo Finance non e' un feed ufficiale con SLA; e' adatto a un
prodotto dimostrativo/educativo. Per uso professionale continuo conviene un
provider a pagamento (Twelve Data, Polygon, ecc.). Il codice e' scritto per
poter sostituire facilmente la sorgente mantenendo la stessa interfaccia.
"""
from __future__ import annotations

import time
import numpy as np

from .data_provider import DataProvider, OHLCVSeries, TIMEFRAME_SECONDS

# Mappa: simbolo interno -> ticker Yahoo Finance
YAHOO_SYMBOL_MAP = {
    "BTC/USDT": "BTC-USD",
    "ETH/USDT": "ETH-USD",
    "XAU/USD": "GC=F",
    "XAG/USD": "SI=F",
    "EUR/USD": "EURUSD=X",
    "GBP/USD": "GBPUSD=X",
    "NAS100": "^NDX",
    "SPX500": "^GSPC",
}

# Fallback per oro/argento se i futures non tornano dati sul timeframe scelto
YAHOO_FALLBACK = {
    "XAU/USD": "XAUUSD=X",
    "XAG/USD": "XAGUSD=X",
}

# Mappa timeframe interno -> intervallo Yahoo
YAHOO_INTERVAL = {
    "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
    "1h": "60m", "4h": "60m",   # 4h non esiste su Yahoo: scarichiamo 1h e ricampioniamo
    "1d": "1d", "1w": "1wk",
}


class YahooDataProvider(DataProvider):
    """Scarica candele reali da Yahoo Finance tramite l'endpoint pubblico
    chart v8 (JSON), senza dipendenze esterne oltre a `requests`."""

    CHART_URLS = [
        "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
        "https://query2.finance.yahoo.com/v8/finance/chart/{symbol}",
    ]

    def __init__(self, timeout: int = 15):
        import requests  # import locale: richiesto solo se si usa questo provider
        self._requests = requests
        self.timeout = timeout

    def _fetch_yahoo(self, yahoo_symbol: str, interval: str, range_: str) -> dict:
        params = {"interval": interval, "range": range_, "includePrePost": "false"}
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json,text/plain,*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://finance.yahoo.com/",
        }
        last_exc: Exception | None = None
        for url_tpl in self.CHART_URLS:
            url = url_tpl.format(symbol=yahoo_symbol)
            try:
                resp = self._requests.get(url, params=params, headers=headers, timeout=self.timeout)
                resp.raise_for_status()
                return resp.json()
            except Exception as exc:  # prova l'host successivo
                last_exc = exc
                continue
        raise last_exc if last_exc else RuntimeError("Fetch Yahoo fallito")

    @staticmethod
    def _range_for(interval: str) -> str:
        # scegliamo il range massimo ragionevole consentito da Yahoo per intervallo
        if interval in ("1m",):
            return "7d"
        if interval in ("5m", "15m", "30m"):
            return "60d"
        if interval in ("60m",):
            return "730d"
        if interval == "1d":
            return "5y"
        if interval == "1wk":
            return "10y"
        return "60d"

    def _parse(self, data: dict, market: str, timeframe: str) -> OHLCVSeries:
        result = data.get("chart", {}).get("result")
        if not result:
            raise ValueError("Risposta Yahoo priva di dati (result vuoto)")
        r0 = result[0]
        timestamps = r0.get("timestamp")
        quote = r0.get("indicators", {}).get("quote", [{}])[0]
        if not timestamps or not quote:
            raise ValueError("Risposta Yahoo priva di serie OHLC")

        o = quote.get("open"); h = quote.get("high")
        l = quote.get("low"); c = quote.get("close")
        v = quote.get("volume")

        ts, op, hi, lo, cl, vo = [], [], [], [], [], []
        for i in range(len(timestamps)):
            # scarta candele con valori nulli (Yahoo inserisce None nei buchi)
            if None in (o[i], h[i], l[i], c[i]):
                continue
            ts.append(float(timestamps[i]))
            op.append(float(o[i])); hi.append(float(h[i]))
            lo.append(float(l[i])); cl.append(float(c[i]))
            vo.append(float(v[i]) if v and v[i] is not None else 0.0)

        if len(ts) < 8:
            raise ValueError("Yahoo ha restituito troppe poche candele valide")

        series = OHLCVSeries(
            market=market, timeframe=timeframe,
            timestamps=np.array(ts), open=np.array(op), high=np.array(hi),
            low=np.array(lo), close=np.array(cl), volume=np.array(vo),
        )

        # 4h non esiste su Yahoo: ricampioniamo da 1h aggregando 4 candele
        if timeframe == "4h":
            series = self._resample_4h(series)
        return series

    @staticmethod
    def _resample_4h(series: OHLCVSeries) -> OHLCVSeries:
        """Aggrega candele 1h in candele 4h (OHLC corretto: open=prima,
        close=ultima, high=max, low=min, volume=somma)."""
        step = 4
        n = len(series.timestamps) // step * step
        ts, op, hi, lo, cl, vo = [], [], [], [], [], []
        for i in range(0, n, step):
            ts.append(series.timestamps[i])
            op.append(series.open[i])
            hi.append(series.high[i:i+step].max())
            lo.append(series.low[i:i+step].min())
            cl.append(series.close[i+step-1])
            vo.append(series.volume[i:i+step].sum())
        return OHLCVSeries(
            market=series.market, timeframe="4h",
            timestamps=np.array(ts), open=np.array(op), high=np.array(hi),
            low=np.array(lo), close=np.array(cl), volume=np.array(vo),
        )

    def get_ohlcv(self, market: str, timeframe: str, start_ts: float, end_ts: float) -> OHLCVSeries:
        if timeframe not in TIMEFRAME_SECONDS:
            raise ValueError(f"Timeframe non supportato: {timeframe}")
        if market not in YAHOO_SYMBOL_MAP:
            raise ValueError(f"Mercato non mappato su Yahoo: {market}")

        interval = YAHOO_INTERVAL[timeframe]
        range_ = self._range_for(interval)
        yahoo_symbol = YAHOO_SYMBOL_MAP[market]

        # tentativo principale
        try:
            data = self._fetch_yahoo(yahoo_symbol, interval, range_)
            series = self._parse(data, market, timeframe)
        except Exception:
            # fallback per oro/argento (spot invece di futures)
            if market in YAHOO_FALLBACK:
                data = self._fetch_yahoo(YAHOO_FALLBACK[market], interval, range_)
                series = self._parse(data, market, timeframe)
            else:
                raise

        # filtra al range richiesto (se l'utente ha selezionato una finestra)
        mask = (series.timestamps >= start_ts) & (series.timestamps <= end_ts)
        if mask.sum() >= 8:
            return OHLCVSeries(
                market=market, timeframe=timeframe,
                timestamps=series.timestamps[mask], open=series.open[mask],
                high=series.high[mask], low=series.low[mask],
                close=series.close[mask], volume=series.volume[mask],
            )
        # se il range richiesto e' troppo stretto o fuori copertura, restituisce
        # tutta la serie disponibile (il frontend mostrera' comunque le candele)
        return series
