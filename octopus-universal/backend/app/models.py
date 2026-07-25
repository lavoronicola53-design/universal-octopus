"""
models.py

Modelli SQLAlchemy per:
- PatternDefinition: la "Pattern Library" (Libro dei Frattali, Pattern 1..57
  + pattern personalizzati assegnati manualmente dall'utente).
- PredictionRecord: il "database statistico" richiesto — ogni previsione
  effettuata viene salvata con i parametri usati e (in un secondo momento,
  quando il tempo reale supera l'orizzonte proiettato) con l'esito reale,
  per calcolare accuracy storica/errore medio nel tempo.
- ScenarioRecord: dettaglio dei singoli scenari generati per una
  previsione (utile per analisi storiche su quale tipo di trasformazione
  tende a essere piu' accurata).
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Float, Integer, Boolean, DateTime, ForeignKey, JSON, Text
)
from sqlalchemy.orm import relationship

from .database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class PatternDefinition(Base):
    """Voce della Pattern Library (Book dei Frattali)."""
    __tablename__ = "pattern_definitions"

    id = Column(String, primary_key=True, default=gen_uuid)
    label = Column(String, nullable=False)          # es. "Pattern 13" o "Pattern personalizzato: Doppio massimo"
    min_candles = Column(Integer, nullable=False)
    max_candles = Column(Integer, nullable=False)
    description = Column(Text, nullable=True)
    is_custom = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class PredictionRecord(Base):
    """Una richiesta di previsione (una sessione Predict) con i suoi
    parametri e, quando disponibile, l'esito reale osservato a posteriori."""
    __tablename__ = "prediction_records"

    id = Column(String, primary_key=True, default=gen_uuid)
    market = Column(String, nullable=False)
    timeframe = Column(String, nullable=False)

    fractal_start_ts = Column(Float, nullable=False)   # primo click
    fractal_end_ts = Column(Float, nullable=False)     # secondo click
    pattern_id = Column(String, ForeignKey("pattern_definitions.id"), nullable=True)

    n_components = Column(Integer, nullable=False)
    horizon = Column(Integer, nullable=False)
    n_scenarios = Column(Integer, nullable=False)

    dominant_scenario_id = Column(String, nullable=False)
    dominant_score = Column(Float, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Esito reale, popolato successivamente da un job/endpoint di verifica
    outcome_recorded = Column(Boolean, default=False)
    outcome_error_pct = Column(Float, nullable=True)     # errore medio % tra proiezione e prezzo reale
    outcome_hit = Column(Boolean, nullable=True)         # il prezzo ha toccato il range target?
    outcome_checked_at = Column(DateTime, nullable=True)

    pattern = relationship("PatternDefinition")
    scenarios = relationship("ScenarioRecord", back_populates="prediction", cascade="all, delete-orphan")


class ScenarioRecord(Base):
    """Dettaglio di un singolo scenario generato in una PredictionRecord."""
    __tablename__ = "scenario_records"

    id = Column(String, primary_key=True, default=gen_uuid)
    prediction_id = Column(String, ForeignKey("prediction_records.id"), nullable=False)

    scenario_label = Column(String, nullable=False)   # "Scenario A", ecc.
    transform_label = Column(String, nullable=False)
    score = Column(Float, nullable=False)
    probability = Column(Float, nullable=False)
    is_dominant = Column(Boolean, default=False)

    metrics_json = Column(JSON, nullable=False)         # ScenarioMetrics serializzate
    future_candles_json = Column(JSON, nullable=False)  # candele sintetiche generate

    prediction = relationship("PredictionRecord", back_populates="scenarios")
