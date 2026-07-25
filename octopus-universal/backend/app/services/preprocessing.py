"""
preprocessing.py

Preprocessing della serie storica (segmento frattale selezionato manualmente
dal trader) prima dell'analisi spettrale.

Pipeline (nell'ordine richiesto dalle specifiche):
    1. Rimozione outlier (clipping IQR)
    2. Resampling / uniformazione della griglia temporale
    3. Detrending (rimozione trend lineare)
    4. Normalizzazione
    5. Filtraggio opzionale (riduzione del rumore, Savitzky-Golay)

Ogni step e' invertibile o tiene traccia dei parametri necessari per
ricostruire la serie originale (trend, scala, offset), perche' la
ricostruzione futura deve tornare in scala di prezzo reale.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import numpy as np

try:
    from scipy.signal import savgol_filter
except ImportError:  # pragma: no cover
    savgol_filter = None


@dataclass
class PreprocessResult:
    """Contiene la serie pre-processata e tutti i parametri per invertire
    la trasformazione quando si ricostruisce/estrapola il prezzo reale."""

    processed: np.ndarray            # serie pronta per la FFT (stazionaria, normalizzata)
    original: np.ndarray              # serie originale (dopo pulizia outlier), scala di prezzo
    trend_slope: float                # coefficiente angolare del trend lineare rimosso
    trend_intercept: float            # intercetta del trend lineare rimosso
    scale: float                      # fattore di scala usato in normalizzazione
    offset: float                     # offset usato in normalizzazione
    dt_seconds: float                 # passo temporale medio (secondi) della griglia ricampionata
    timestamps: np.ndarray            # timestamp (epoch seconds) allineati a `processed`
    meta: dict = field(default_factory=dict)

    def denormalize(self, values: np.ndarray) -> np.ndarray:
        """Inverte normalizzazione (non il detrend: va fatto separatamente
        con `add_trend`, perche' il trend va esteso nel futuro)."""
        return values * self.scale + self.offset

    def add_trend(self, values: np.ndarray, start_index: int) -> np.ndarray:
        """Riaggiunge il trend lineare, valutato a partire da `start_index`
        (indice nella serie originale, puo' essere > len(original) per il futuro)."""
        idx = np.arange(start_index, start_index + len(values))
        trend = self.trend_slope * idx + self.trend_intercept
        return values + trend


def remove_outliers(series: np.ndarray, iqr_multiplier: float = 3.0) -> np.ndarray:
    """Clip degli outlier basato su IQR (Interquartile Range). Non rimuove
    punti (manterrebbe la griglia temporale intatta) ma li clippa ai bound,
    cosi' non introducono discontinuita' spurie nello spettro."""
    q1, q3 = np.percentile(series, [25, 75])
    iqr = q3 - q1
    if iqr == 0:
        return series.copy()
    lower = q1 - iqr_multiplier * iqr
    upper = q3 + iqr_multiplier * iqr
    return np.clip(series, lower, upper)


def resample_uniform(timestamps: np.ndarray, values: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
    """Ricampiona su una griglia temporale uniforme tramite interpolazione
    lineare. Le candele dovrebbero gia' essere a passo fisso, ma eventuali
    barre mancanti (festivita', manutenzione exchange) vengono qui
    interpolate per non introdurre falsi salti di frequenza nella FFT."""
    if len(timestamps) < 2:
        raise ValueError("Servono almeno 2 punti per il resampling")
    dt = float(np.median(np.diff(timestamps)))
    if dt <= 0:
        raise ValueError("Timestamp non monotoni crescenti")
    n = int(round((timestamps[-1] - timestamps[0]) / dt)) + 1
    grid = timestamps[0] + dt * np.arange(n)
    resampled = np.interp(grid, timestamps, values)
    return grid, resampled, dt


def detrend_linear(values: np.ndarray) -> tuple[np.ndarray, float, float]:
    """Rimuove un trend lineare (least squares). Ritorna la serie detrended
    e i coefficienti (slope, intercept) per poterlo riestendere nel futuro."""
    x = np.arange(len(values))
    slope, intercept = np.polyfit(x, values, 1)
    trend = slope * x + intercept
    return values - trend, float(slope), float(intercept)


def normalize(values: np.ndarray) -> tuple[np.ndarray, float, float]:
    """Normalizzazione min-max in [-1, 1]. Ritorna anche scale/offset per
    l'inversione (values = normalized * scale + offset)."""
    v_min, v_max = float(values.min()), float(values.max())
    if v_max == v_min:
        return np.zeros_like(values), 1.0, v_min
    scale = (v_max - v_min) / 2.0
    offset = (v_max + v_min) / 2.0
    normalized = (values - offset) / scale
    return normalized, scale, offset


def smooth_savgol(values: np.ndarray, window_fraction: float = 0.05) -> np.ndarray:
    """Filtro Savitzky-Golay opzionale per riduzione del rumore ad alta
    frequenza prima della FFT. Non applicato se scipy non e' disponibile o
    se la serie e' troppo corta per la finestra richiesta."""
    n = len(values)
    if savgol_filter is None or n < 9:
        return values
    window = max(5, int(n * window_fraction) | 1)  # forza dispari
    window = min(window, n - 1 if (n - 1) % 2 == 1 else n - 2)
    if window < 5:
        return values
    polyorder = min(3, window - 2)
    try:
        return savgol_filter(values, window_length=window, polyorder=polyorder)
    except Exception:
        return values


def preprocess_segment(
    timestamps: np.ndarray,
    close_prices: np.ndarray,
    *,
    remove_outliers_flag: bool = True,
    apply_smoothing: bool = False,
    iqr_multiplier: float = 3.0,
) -> PreprocessResult:
    """Pipeline completa di preprocessing sul segmento frattale selezionato
    dall'utente (timestamps in epoch seconds, close_prices allineati)."""
    if len(timestamps) != len(close_prices):
        raise ValueError("timestamps e close_prices devono avere la stessa lunghezza")
    if len(timestamps) < 8:
        raise ValueError("Il frattale selezionato deve contenere almeno 8 candele")

    series = np.asarray(close_prices, dtype=np.float64)
    if remove_outliers_flag:
        series = remove_outliers(series, iqr_multiplier)

    grid_ts, resampled, dt = resample_uniform(np.asarray(timestamps, dtype=np.float64), series)

    original = resampled.copy()

    detrended, slope, intercept = detrend_linear(resampled)

    if apply_smoothing:
        detrended = smooth_savgol(detrended)

    normalized, scale, offset = normalize(detrended)

    return PreprocessResult(
        processed=normalized,
        original=original,
        trend_slope=slope,
        trend_intercept=intercept,
        scale=scale,
        offset=offset,
        dt_seconds=dt,
        timestamps=grid_ts,
        meta={"n_points": len(normalized), "smoothing_applied": apply_smoothing},
    )
