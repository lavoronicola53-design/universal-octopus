"""
candle_synthesis.py

Trasforma una curva di prezzo (close price proiettato, continuo) in vere
candele OHLC future, come richiesto: la previsione principale non deve
essere una linea ma un set di candele con Open/High/Low/Close/Timestamp
(e Volume sintetico opzionale).

Metodologia:
- Close[t]  = valore proiettato al tempo t
- Open[t]   = Close[t-1] (continuita' tra candele consecutive), con la
              prima Open = ultimo Close storico osservato
- volatilita' locale stimata dalla volatilita' storica recente (range
  medio delle ultime `vol_lookback` candele osservate), usata per
  generare wick (ombre) e per l'ampiezza body/wick in modo coerente con
  il comportamento storico dell'asset
- High[t] = max(Open, Close) + wick_up
- Low[t]  = min(Open, Close) - wick_down
- Volume sintetico (opzionale) = media storica +/- rumore proporzionale

Il rumore usato per i wick e il volume e' deterministico rispetto a un
seed (derivato dallo scenario), cosi' la stessa richiesta produce sempre
lo stesso output (riproducibilita').
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np


@dataclass
class SyntheticCandle:
    timestamp: float
    open: float
    high: float
    low: float
    close: float
    volume: float | None = None
    synthetic: bool = True

    def to_dict(self) -> dict:
        d = {
            "timestamp": self.timestamp,
            "open": round(self.open, 8),
            "high": round(self.high, 8),
            "low": round(self.low, 8),
            "close": round(self.close, 8),
            "synthetic": self.synthetic,
        }
        if self.volume is not None:
            d["volume"] = round(self.volume, 4)
        return d


def estimate_local_volatility(historical_high: np.ndarray, historical_low: np.ndarray,
                               historical_close: np.ndarray, lookback: int = 20) -> float:
    """Stima la volatilita' locale come range medio (high-low) delle
    ultime `lookback` candele storiche, normalizzato sul prezzo medio,
    cosi' da poter essere applicato in scala assoluta ai prezzi futuri."""
    lb = min(lookback, len(historical_close))
    ranges = historical_high[-lb:] - historical_low[-lb:]
    avg_price = float(np.mean(historical_close[-lb:])) or 1.0
    return float(np.mean(ranges)) / avg_price if avg_price else 0.0


def synthesize_future_candles(
    close_path: np.ndarray,
    last_close: float,
    dt_seconds: float,
    last_timestamp: float,
    local_volatility_pct: float,
    avg_volume: float | None,
    seed: int,
) -> list[SyntheticCandle]:
    """Genera una lista di candele OHLC sintetiche a partire dalla curva
    di close proiettata (in scala di prezzo reale, gia' denormalizzata e
    con trend riaggiunto)."""
    rng = np.random.default_rng(seed)
    n = len(close_path)
    candles: list[SyntheticCandle] = []

    prev_close = last_close
    for i in range(n):
        close = float(close_path[i])
        open_ = prev_close
        body_high = max(open_, close)
        body_low = min(open_, close)
        body_size = abs(close - open_)

        # I wick (ombre) sono proporzionati sia alla volatilita' storica
        # locale sia al corpo della candela: una candela con corpo piccolo
        # avra' ombre piccole, evitando ombre sproporzionate/"strane". La
        # componente casuale e' contenuta (scala ridotta) e deterministica
        # rispetto al seed, cosi' l'output e' riproducibile e realistico.
        vol_component = local_volatility_pct * abs(close if close != 0 else 1.0)
        wick_scale = 0.5 * vol_component + 0.25 * body_size
        wick_up = abs(rng.normal(loc=wick_scale * 0.4, scale=wick_scale * 0.15))
        wick_down = abs(rng.normal(loc=wick_scale * 0.4, scale=wick_scale * 0.15))

        high = body_high + wick_up
        low = body_low - wick_down

        volume = None
        if avg_volume is not None:
            volume = max(0.0, avg_volume * (1.0 + rng.normal(0, 0.2)))

        ts = last_timestamp + dt_seconds * (i + 1)
        candles.append(SyntheticCandle(
            timestamp=ts, open=open_, high=high, low=low, close=close, volume=volume,
        ))
        prev_close = close

    return candles
