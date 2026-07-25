"""
book_shapes.py

Forme geometriche di riferimento dei pattern del "Libro dei Frattali",
usate da pattern_matching.py per riconoscere quale pattern il frattale
selezionato dall'operatore assomiglia di piu' (per struttura, non per
numero di candele).

Ogni forma e' una sequenza di valori di chiusura NORMALIZZATI che descrive
l'andamento caratteristico del pattern. I valori sono relativi (la scala
non conta: il matching normalizza tutto), conta solo la forma.

Le forme dei pattern documentati nel PDF (1, 3, 11, 13, 15) sono modellate
sulla loro descrizione/figura. Gli altri pattern del Libro possono essere
aggiunti qui con la loro sequenza caratteristica; in assenza di una forma
esplicita non vengono inclusi nel confronto (meglio non confrontare che
confrontare con una forma inventata).

NOTA: queste forme sono una ricostruzione della struttura visiva dei
pattern come descritti nel materiale sorgente. Se disponi delle coordinate
esatte dei pattern dal Libro originale, puoi sostituirle qui per un
matching piu' fedele.
"""
from __future__ import annotations

import numpy as np
from .pattern_matching import PatternShape


# Forme caratteristiche (sequenze di chiusura relative). La forma descrive
# l'ANDAMENTO: numeri crescenti = salita, decrescenti = discesa.
_RAW_SHAPES: dict[str, tuple[str, list[float]]] = {
    # Pattern 1: forte candela ribassista iniziale, poi consolidamento e
    # ripartenza rialzista graduale (descritto su BTC/ETH/Oro/Argento).
    "Pattern 1": ("Pattern 1", [10, 3, 3.5, 4.5, 4.2, 5.2, 6.0]),

    # Pattern 3: range 3-6 candele, discesa iniziale piu' dolce poi rimbalzo
    # con inclinazione diversa dal Pattern 1.
    "Pattern 3": ("Pattern 3", [8, 6, 4, 5, 6.5, 7]),

    # Pattern 11: struttura a doppia gamba (due minimi) prima della ripresa.
    "Pattern 11": ("Pattern 11", [7, 4, 5.5, 3.8, 5, 6.5, 6]),

    # Pattern 13: pattern complesso = Pattern 3 seguito da estensione
    # rialzista (contiene Pattern 3 al suo interno).
    "Pattern 13": ("Pattern 13", [8, 6, 4, 5, 6.5, 7, 6.8, 7.5, 8.2, 9]),

    # Pattern 15: struttura piu' articolata con doppio massimo/minimo
    # (verificato anche su Trump Media nel materiale sorgente).
    "Pattern 15": ("Pattern 15", [6, 7.5, 6.2, 5, 5.5, 6.8, 6.4, 4.5, 4]),
}


def get_book_shapes() -> list[PatternShape]:
    """Ritorna la lista delle forme di riferimento dei pattern del Libro."""
    shapes: list[PatternShape] = []
    for pid, (label, seq) in _RAW_SHAPES.items():
        shapes.append(PatternShape(
            pattern_id=pid,
            label=label,
            shape=np.array(seq, dtype=np.float64),
        ))
    return shapes
