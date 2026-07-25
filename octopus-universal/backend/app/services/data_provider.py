"""
data_provider.py

Livello di astrazione per l'accesso ai dati OHLCV. Il software NON deve
riconoscere pattern automaticamente: questo modulo si occupa solo di
fornire le candele storiche al frontend/al motore, in modo che sia il
trader a selezionare manualmente il segmento frattale.

Implementazioni fornite:

- SyntheticDataProvider: generatore deterministico (seed) di dati
  realistici per demo/sviluppo/test, quando non sono disponibili
  credenziali per un feed reale. Non richiede rete.
- CCXTDataProvider: integrazione con exchange crypto reali (Binance, ecc.)
  tramite la libreria `ccxt`. Richiede pacchetto `ccxt` installato e
  accesso di rete in produzione; non viene mai eseguita nei test/demo di
  questo repository.
- CSVDataProvider: carica OHLCV da file CSV locale (utile per importare
  dataset storici per oro/argento/forex se non si dispone di un feed
  realtime dedicato).

Il router FastAPI seleziona il provider da usare tramite `get_provider()`
in base alla configurazione (`app/config.py`).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import numpy as np
import pandas as pd


TIMEFRAME_SECONDS = {
    "1m": 60, "5m": 300, "15m": 900, "30m": 1800,
    "1h": 3600, "4h": 14400, "1d": 86400, "1w": 604800,
}

SUPPORTED_MARKETS = [
    "BTC/USDT", "ETH/USDT", "XAU/USD", "XAG/USD",
    "EUR/USD", "GBP/USD", "NAS100", "SPX500",
]


@dataclass
class OHLCVSeries:
    market: str
    timeframe: str
    timestamps: np.ndarray   # epoch seconds, ordine crescente
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    volume: np.ndarray

    def slice_between(self, start_ts: float, end_ts: float) -> "OHLCVSeries":
        mask = (self.timestamps >= start_ts) & (self.timestamps <= end_ts)
        if mask.sum() < 8:
            raise ValueError(
                "Il segmento selezionato contiene meno di 8 candele: "
                "seleziona un frattale piu' ampio."
            )
        return OHLCVSeries(
            market=self.market, timeframe=self.timeframe,
            timestamps=self.timestamps[mask], open=self.open[mask],
            high=self.high[mask], low=self.low[mask],
            close=self.close[mask], volume=self.volume[mask],
        )

    def to_records(self) -> list[dict]:
        return [
            {
                "timestamp": float(self.timestamps[i]),
                "open": float(self.open[i]), "high": float(self.high[i]),
                "low": float(self.low[i]), "close": float(self.close[i]),
                "volume": float(self.volume[i]),
            }
            for i in range(len(self.timestamps))
        ]


class DataProvider(ABC):
    @abstractmethod
    def get_ohlcv(self, market: str, timeframe: str, start_ts: float, end_ts: float) -> OHLCVSeries:
        ...


class SyntheticDataProvider(DataProvider):
    """Generatore deterministico di serie storiche plausibili, usato come
    default quando non e' configurato un provider di dati reale. Il seed
    e' derivato da market+timeframe, cosi' la stessa combinazione produce
    sempre la stessa serie (riproducibilita' per demo/test)."""

    def __init__(self, base_price: dict[str, float] | None = None):
        self.base_price = base_price or {
            "BTC/USDT": 65000.0, "ETH/USDT": 3200.0, "XAU/USD": 2650.0,
            "XAG/USD": 30.5, "EUR/USD": 1.08, "GBP/USD": 1.27,
            "NAS100": 20500.0, "SPX500": 5900.0,
        }

    def _seed_for(self, market: str, timeframe: str) -> int:
        return abs(hash((market, timeframe))) % (2 ** 32)

    def get_ohlcv(self, market: str, timeframe: str, start_ts: float, end_ts: float) -> OHLCVSeries:
        if timeframe not in TIMEFRAME_SECONDS:
            raise ValueError(f"Timeframe non supportato: {timeframe}")
        dt = TIMEFRAME_SECONDS[timeframe]
        n = max(8, int((end_ts - start_ts) / dt) + 1)
        rng = np.random.default_rng(self._seed_for(market, timeframe))

        price0 = self.base_price.get(market, 100.0)
        vol_pct = 0.004 if "USD" in market and "/" in market else 0.003
        drift = rng.normal(0, 0.0002, n)
        shocks = rng.normal(0, vol_pct, n)
        log_returns = drift + shocks
        close = price0 * np.exp(np.cumsum(log_returns))

        open_ = np.empty(n)
        open_[0] = price0
        open_[1:] = close[:-1]
        wig = np.abs(rng.normal(vol_pct * 0.6, vol_pct * 0.3, n)) * close
        high = np.maximum(open_, close) + wig
        low = np.minimum(open_, close) - wig
        volume = np.abs(rng.normal(1000, 200, n)) * (price0 / 100.0)

        timestamps = start_ts + dt * np.arange(n)

        return OHLCVSeries(
            market=market, timeframe=timeframe, timestamps=timestamps,
            open=open_, high=high, low=low, close=close, volume=volume,
        )


class CCXTDataProvider(DataProvider):
    """Provider per dati crypto reali via ccxt (es. Binance). Da attivare
    in produzione impostando DATA_PROVIDER=ccxt e le credenziali exchange
    nelle variabili d'ambiente (vedi app/config.py). Richiede accesso di
    rete e il pacchetto `ccxt` installato (requirements.txt)."""

    def __init__(self, exchange_id: str = "binance", api_key: str | None = None, api_secret: str | None = None):
        try:
            import ccxt  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "Il pacchetto 'ccxt' non e' installato. Aggiungilo a requirements.txt "
                "e installalo per usare dati crypto live."
            ) from exc
        self._ccxt = ccxt
        klass = getattr(ccxt, exchange_id)
        self.exchange = klass({"apiKey": api_key, "secret": api_secret, "enableRateLimit": True})

    def get_ohlcv(self, market: str, timeframe: str, start_ts: float, end_ts: float) -> OHLCVSeries:
        symbol = market.replace("XAU/USD", "PAXG/USDT")  # esempio di mapping asset non-crypto
        since_ms = int(start_ts * 1000)
        all_rows: list[list[float]] = []
        while True:
            batch = self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=since_ms, limit=1000)
            if not batch:
                break
            all_rows.extend(batch)
            last_ts = batch[-1][0]
            if last_ts / 1000 >= end_ts or len(batch) < 1000:
                break
            since_ms = last_ts + 1
        if not all_rows:
            raise ValueError("Nessun dato restituito dall'exchange per il range richiesto.")
        arr = np.array(all_rows, dtype=np.float64)
        mask = (arr[:, 0] / 1000 >= start_ts) & (arr[:, 0] / 1000 <= end_ts)
        arr = arr[mask]
        return OHLCVSeries(
            market=market, timeframe=timeframe,
            timestamps=arr[:, 0] / 1000.0, open=arr[:, 1], high=arr[:, 2],
            low=arr[:, 3], close=arr[:, 4], volume=arr[:, 5],
        )


class CSVDataProvider(DataProvider):
    """Carica OHLCV da CSV locale con colonne: timestamp,open,high,low,close,volume
    (timestamp in epoch seconds). Utile per dataset storici oro/argento/
    forex importati manualmente."""

    def __init__(self, csv_paths: dict[str, str]):
        # csv_paths: {"XAU/USD:1h": "/data/xauusd_1h.csv", ...}
        self.csv_paths = csv_paths
        self._cache: dict[str, pd.DataFrame] = {}

    def _load(self, key: str) -> pd.DataFrame:
        if key not in self._cache:
            path = self.csv_paths[key]
            df = pd.read_csv(path)
            df = df.sort_values("timestamp").reset_index(drop=True)
            self._cache[key] = df
        return self._cache[key]

    def get_ohlcv(self, market: str, timeframe: str, start_ts: float, end_ts: float) -> OHLCVSeries:
        key = f"{market}:{timeframe}"
        if key not in self.csv_paths:
            raise ValueError(f"Nessun CSV configurato per {key}")
        df = self._load(key)
        mask = (df["timestamp"] >= start_ts) & (df["timestamp"] <= end_ts)
        sub = df.loc[mask]
        if len(sub) < 8:
            raise ValueError("Range troppo corto nel CSV per il market/timeframe richiesto.")
        return OHLCVSeries(
            market=market, timeframe=timeframe,
            timestamps=sub["timestamp"].to_numpy(dtype=np.float64),
            open=sub["open"].to_numpy(dtype=np.float64),
            high=sub["high"].to_numpy(dtype=np.float64),
            low=sub["low"].to_numpy(dtype=np.float64),
            close=sub["close"].to_numpy(dtype=np.float64),
            volume=sub["volume"].to_numpy(dtype=np.float64),
        )


_provider_instance: DataProvider | None = None


def get_provider() -> DataProvider:
    """Factory usata dai router. Legge la configurazione da app.config e
    istanzia (una sola volta) il provider corretto. Default: sintetico."""
    global _provider_instance
    if _provider_instance is not None:
        return _provider_instance

    from ..config import settings

    if settings.data_provider == "ccxt":
        _provider_instance = CCXTDataProvider(
            exchange_id=settings.ccxt_exchange,
            api_key=settings.ccxt_api_key,
            api_secret=settings.ccxt_api_secret,
        )
    elif settings.data_provider == "yahoo":
        from .yahoo_provider import YahooDataProvider
        _provider_instance = YahooDataProvider()
    elif settings.data_provider == "real":
        from .realdata_provider import RealDataProvider
        _provider_instance = RealDataProvider()
    elif settings.data_provider == "csv":
        _provider_instance = CSVDataProvider(csv_paths=settings.csv_paths)
    else:
        _provider_instance = SyntheticDataProvider()

    return _provider_instance
