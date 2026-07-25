"""
scoring.py

Calcolo delle metriche oggettive di qualita' per ogni scenario generato e
combinazione in uno score finale + probabilita' relativa (softmax).

Metriche implementate (tutte calcolabili realmente dai dati, nessuna e'
una "black box"):

- reconstruction_error : RMSE normalizzato tra la storia ricostruita con le
  top-N componenti e la storia osservata reale. Misura quanto bene le
  componenti selezionate spiegano il passato (piu' basso e' meglio).
- correlation          : correlazione di Pearson tra storia ricostruita e
  storia osservata.
- spectral_coherence   : frazione di energia spettrale totale concentrata
  nelle componenti selezionate (energy_selected / energy_total).
- harmonic_continuity  : continuita' di primo ordine (derivata) tra
  l'ultimo tratto della storia ricostruita e il primo tratto della
  proiezione futura (discontinuita' basse = piu' plausibile).
- snr                  : rapporto segnale-rumore, energia delle componenti
  dominanti selezionate rispetto al residuo (storia osservata - storia
  ricostruita).
- fractal_similarity   : autocorrelazione del segmento storico selezionato
  rispetto a se stesso su lag multipli della propria lunghezza (proxy di
  auto-similarita' frattale/ciclica, calcolabile senza dati esterni).

Nota: "stabilita' multi-timeframe" richiede il confronto con la stessa
analisi su un altro timeframe della stessa serie; e' esposta come hook
opzionale (multi_timeframe_stability) che il chiamante puo' valorizzare se
dispone di un secondo timeframe pre-calcolato, altrimenti viene assegnato
un valore neutro (0.5) per non falsare lo score complessivo.
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np


@dataclass
class ScenarioMetrics:
    reconstruction_error: float
    correlation: float
    spectral_coherence: float
    harmonic_continuity: float
    snr: float
    fractal_similarity: float
    multi_timeframe_stability: float = 0.5

    def weighted_score(self, weights: dict[str, float] | None = None) -> float:
        w = weights or {
            "reconstruction_error": 0.25,   # peso negativo (errore -> penalizza)
            "correlation": 0.20,
            "spectral_coherence": 0.15,
            "harmonic_continuity": 0.15,
            "snr": 0.15,
            "fractal_similarity": 0.05,
            "multi_timeframe_stability": 0.05,
        }
        score = (
            w["reconstruction_error"] * (1.0 - min(self.reconstruction_error, 1.0))
            + w["correlation"] * max(self.correlation, 0.0)
            + w["spectral_coherence"] * self.spectral_coherence
            + w["harmonic_continuity"] * self.harmonic_continuity
            + w["snr"] * min(self.snr / (self.snr + 1.0), 1.0)
            + w["fractal_similarity"] * self.fractal_similarity
            + w["multi_timeframe_stability"] * self.multi_timeframe_stability
        )
        return float(np.clip(score, 0.0, 1.0))


def reconstruction_error(observed: np.ndarray, reconstructed: np.ndarray) -> float:
    rmse = float(np.sqrt(np.mean((observed - reconstructed) ** 2)))
    norm = float(np.std(observed)) or 1e-9
    return rmse / norm


def correlation(observed: np.ndarray, reconstructed: np.ndarray) -> float:
    if np.std(observed) == 0 or np.std(reconstructed) == 0:
        return 0.0
    return float(np.corrcoef(observed, reconstructed)[0, 1])


def spectral_coherence(energy_selected: float, energy_total: float) -> float:
    return float(np.clip(energy_selected / max(energy_total, 1e-12), 0.0, 1.0))


def harmonic_continuity(history_end: np.ndarray, future_start: np.ndarray) -> float:
    """Confronta la derivata discreta a cavallo del punto di giunzione
    passato/futuro: continuita' alta -> discontinuita' bassa -> score alto."""
    if len(history_end) < 2 or len(future_start) < 2:
        return 0.5
    d_hist = history_end[-1] - history_end[-2]
    d_fut = future_start[1] - future_start[0]
    jump = future_start[0] - history_end[-1]
    slope_diff = abs(d_fut - d_hist)
    denom = (abs(d_hist) + abs(d_fut) + abs(jump) + 1e-9)
    discontinuity = (slope_diff + abs(jump)) / denom
    return float(np.clip(1.0 - discontinuity, 0.0, 1.0))


def signal_to_noise_ratio(observed: np.ndarray, reconstructed: np.ndarray) -> float:
    residual = observed - reconstructed
    signal_power = float(np.mean(reconstructed ** 2))
    noise_power = float(np.mean(residual ** 2)) or 1e-12
    return signal_power / noise_power


def fractal_self_similarity(segment: np.ndarray) -> float:
    """Autocorrelazione normalizzata calcolata su lag = meta' lunghezza
    segmento, come proxy di auto-similarita' ciclica del pattern
    selezionato (piu' alta = pattern piu' "regolare"/ripetitivo)."""
    n = len(segment)
    if n < 4:
        return 0.5
    lag = max(1, n // 2)
    a = segment[:-lag]
    b = segment[lag:]
    if np.std(a) == 0 or np.std(b) == 0:
        return 0.5
    corr = np.corrcoef(a, b)[0, 1]
    return float(np.clip((corr + 1) / 2, 0.0, 1.0))


def score_scenario(
    observed_history: np.ndarray,
    reconstructed_history: np.ndarray,
    future_projection: np.ndarray,
    energy_selected: float,
    energy_total: float,
    multi_timeframe_stability: float | None = None,
) -> ScenarioMetrics:
    return ScenarioMetrics(
        reconstruction_error=reconstruction_error(observed_history, reconstructed_history),
        correlation=correlation(observed_history, reconstructed_history),
        spectral_coherence=spectral_coherence(energy_selected, energy_total),
        harmonic_continuity=harmonic_continuity(reconstructed_history, future_projection),
        snr=signal_to_noise_ratio(observed_history, reconstructed_history),
        fractal_similarity=fractal_self_similarity(observed_history),
        multi_timeframe_stability=(
            multi_timeframe_stability if multi_timeframe_stability is not None else 0.5
        ),
    )


def rank_scenarios(scores: list[float]) -> np.ndarray:
    """Converte una lista di score grezzi [0,1] in probabilita' relative
    tramite softmax (temperatura fissa), cosi' che la somma faccia 1 e gli
    scenari con score piu' alto abbiano probabilita' relativa maggiore in
    modo monotono e differenziabile."""
    arr = np.asarray(scores, dtype=np.float64)
    temperature = 0.15
    exp = np.exp((arr - arr.max()) / temperature)
    return exp / exp.sum()
