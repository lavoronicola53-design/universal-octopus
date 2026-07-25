"""
pattern_matching.py

Riconoscimento del pattern del "Libro dei Frattali" piu' simile al frattale
selezionato dall'operatore, confrontando la STRUTTURA GEOMETRICA (la forma
della curva dei prezzi) e NON il numero di candele.

Metodo:
1. Ogni pattern del Libro e' descritto da una sequenza di valori di chiusura
   (la sua "forma"). Il frattale selezionato dall'utente e' anch'esso una
   sequenza di chiusure.
2. Entrambi vengono portati alla stessa scala:
      - ricampionati a una lunghezza comune (default 64 punti) tramite
        interpolazione lineare  -> rende confrontabili forme con numero di
        candele diverso;
      - normalizzati in ampiezza (z-score)  -> rende confrontabili forme con
        escursioni di prezzo diverse.
3. La somiglianza e' misurata combinando:
      - correlazione di Pearson tra le due forme normalizzate (cattura
        l'andamento complessivo);
      - 1 - distanza euclidea normalizzata (cattura gli scostamenti locali).
   Si prova anche la forma speculare orizzontale (pattern ribaltato nel
   tempo) e si tiene il punteggio migliore, perche' un pattern del Libro puo'
   comparire anche "riflesso".
4. Ritorna il pattern del Libro col punteggio piu' alto.

Questo modulo NON serve a fare la previsione (quella e' solo Fourier): serve
a dire all'operatore "il frattale che hai selezionato assomiglia al Pattern N
del Libro", come riferimento didattico.
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np


@dataclass
class PatternShape:
    """Forma geometrica di riferimento di un pattern del Libro."""
    pattern_id: str
    label: str
    shape: np.ndarray  # sequenza di chiusure che descrive la forma


@dataclass
class MatchResult:
    pattern_id: str
    label: str
    similarity: float          # 0..1
    mirrored: bool             # True se il match migliore e' con la forma speculare


def _resample(series: np.ndarray, n: int = 64) -> np.ndarray:
    """Ricampiona una sequenza a lunghezza fissa n via interpolazione
    lineare, cosi' forme con numero di candele diverso diventano
    confrontabili punto-a-punto."""
    if len(series) == n:
        return series.astype(np.float64)
    x_old = np.linspace(0.0, 1.0, len(series))
    x_new = np.linspace(0.0, 1.0, n)
    return np.interp(x_new, x_old, series).astype(np.float64)


def _zscore(series: np.ndarray) -> np.ndarray:
    """Normalizza in ampiezza (media 0, deviazione 1). Rende la forma
    indipendente dal livello di prezzo e dall'escursione assoluta."""
    std = series.std()
    if std < 1e-12:
        return np.zeros_like(series)
    return (series - series.mean()) / std


def _shape_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Somiglianza geometrica tra due forme gia' ricampionate e
    normalizzate, in [0, 1]. Combina correlazione e distanza euclidea."""
    # correlazione di Pearson (andamento complessivo)
    if a.std() < 1e-12 or b.std() < 1e-12:
        corr = 0.0
    else:
        corr = float(np.corrcoef(a, b)[0, 1])
    corr01 = (corr + 1.0) / 2.0  # da [-1,1] a [0,1]

    # distanza euclidea normalizzata (scostamenti locali)
    dist = float(np.sqrt(np.mean((a - b) ** 2)))
    # per z-score la distanza tipica tra forme scorrelate e' ~sqrt(2); mappiamo
    dist01 = float(np.clip(1.0 - dist / np.sqrt(2.0), 0.0, 1.0))

    # media pesata: diamo piu' peso alla correlazione (andamento) che alla
    # distanza puntuale
    return 0.65 * corr01 + 0.35 * dist01


def match_pattern(selected_closes: np.ndarray, book: list[PatternShape],
                  resample_n: int = 64) -> MatchResult | None:
    """Trova il pattern del Libro geometricamente piu' simile al frattale
    selezionato (`selected_closes` = chiusure del segmento scelto)."""
    if len(selected_closes) < 3 or not book:
        return None

    target = _zscore(_resample(np.asarray(selected_closes, dtype=np.float64), resample_n))

    best: MatchResult | None = None
    for entry in book:
        if len(entry.shape) < 3:
            continue
        ref = _zscore(_resample(entry.shape, resample_n))

        sim_normal = _shape_similarity(target, ref)
        sim_mirror = _shape_similarity(target, ref[::-1])  # pattern riflesso nel tempo

        mirrored = sim_mirror > sim_normal
        sim = max(sim_normal, sim_mirror)

        if best is None or sim > best.similarity:
            best = MatchResult(
                pattern_id=entry.pattern_id, label=entry.label,
                similarity=float(sim), mirrored=mirrored,
            )

    return best
