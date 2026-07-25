"""
seed_patterns.py

Popola la Pattern Library con le 57 voci previste ("Pattern 1" ... "Pattern
57"), organizzate nei range dichiarati nella documentazione teorica
(3-6, 6-12, 12-24, 24-39, 39-56 candele). Le fonti allegate descrivono
esplicitamente solo alcuni pattern con dettaglio grafico (es. Pattern 1, 3,
11, 13, 15); per le voci non dettagliate nel materiale sorgente questo
script crea comunque il record con range coerente e una descrizione
generica, cosi' che l'utente possa arricchirla manualmente dall'interno
dell'app (endpoint PATCH non incluso di default: creare via API se serve).

Eseguire con: `python -m app.seed_patterns` (dentro il container backend).
"""
from __future__ import annotations

from .database import SessionLocal, init_db
from . import models

# Range dichiarati nella documentazione (numero di candele min-max)
RANGE_BUCKETS = [
    (3, 6, 1, 14),     # Pattern 1..14 circa nel range 3-6 (incl. i Pattern 1,3,11,13 descritti)
    (6, 12, 15, 28),
    (12, 24, 29, 40),
    (24, 39, 41, 50),
    (39, 56, 51, 57),
]

# Pattern esplicitamente descritti/illustrati nel PDF sorgente, con nota
DOCUMENTED = {
    1: "Pattern di riferimento base (3-6 candele): candela ribassista iniziale seguita da consolidamento e ripartenza, osservato identico su BTC, ETH, Oro, Argento nel materiale sorgente.",
    3: "Variante del range 3-6 candele con inclinazione/curvatura differente da Pattern 1; componente base di pattern complessi come Pattern 13.",
    11: "Pattern del range 3-6 candele con struttura a doppia gamba; compare come componente di Pattern 13.",
    13: "Pattern complesso che integra al suo interno Pattern 3 e Pattern 11; verificato su BTC, ETH, Oro, Argento nel materiale sorgente.",
    15: "Pattern verificato anche sul titolo Trump Media & Technology Group Corp (NASDAQ) nell'esempio del 12 luglio 2024 citato nel materiale sorgente.",
}


def seed() -> None:
    init_db()
    db = SessionLocal()
    try:
        existing = {p.label for p in db.query(models.PatternDefinition).all()}
        for lo, hi, start_n, end_n in RANGE_BUCKETS:
            for n in range(start_n, end_n + 1):
                label = f"Pattern {n}"
                if label in existing:
                    continue
                description = DOCUMENTED.get(
                    n,
                    f"Voce della Pattern Library nel range {lo}-{hi} candele. "
                    "Descrizione da completare manualmente dall'utente.",
                )
                db.add(models.PatternDefinition(
                    label=label, min_candles=lo, max_candles=hi,
                    description=description, is_custom=False,
                ))
        db.commit()
        print("Seed completato:", db.query(models.PatternDefinition).count(), "pattern totali")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
