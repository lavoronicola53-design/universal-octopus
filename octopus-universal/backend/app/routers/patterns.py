"""
routers/patterns.py

- CRUD minimale sulla Pattern Library (Book dei Frattali: Pattern 1..57 +
  pattern personalizzati).
- Endpoint per registrare l'esito reale di una previsione gia' effettuata
  (necessario per calcolare frequenza/percentuale di successo/errore medio
  richiesti dal "database statistico").
- Endpoint di sintesi statistiche (accuracy storica).
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime

from ..database import get_db
from .. import models
from ..schemas import (
    PatternDefinitionSchema, PatternCreateRequest,
    OutcomeUpdateRequest, AccuracyStatsResponse,
)

router = APIRouter(prefix="/api/patterns", tags=["patterns"])
stats_router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("", response_model=list[PatternDefinitionSchema])
def list_patterns(db: Session = Depends(get_db)):
    return db.query(models.PatternDefinition).order_by(models.PatternDefinition.min_candles).all()


@router.post("", response_model=PatternDefinitionSchema)
def create_pattern(payload: PatternCreateRequest, db: Session = Depends(get_db)):
    if payload.max_candles < payload.min_candles:
        raise HTTPException(400, "max_candles deve essere >= min_candles")
    pattern = models.PatternDefinition(
        label=payload.label,
        min_candles=payload.min_candles,
        max_candles=payload.max_candles,
        description=payload.description,
        is_custom=True,
    )
    db.add(pattern)
    db.commit()
    db.refresh(pattern)
    return pattern


@stats_router.post("/outcome")
def record_outcome(payload: OutcomeUpdateRequest, db: Session = Depends(get_db)):
    """Registra l'esito reale (osservato a posteriori, quando il tempo
    reale ha superato l'orizzonte proiettato) per una previsione salvata."""
    record = db.query(models.PredictionRecord).filter_by(id=payload.prediction_id).first()
    if record is None:
        raise HTTPException(404, "Previsione non trovata")
    record.outcome_recorded = True
    record.outcome_error_pct = payload.outcome_error_pct
    record.outcome_hit = payload.outcome_hit
    record.outcome_checked_at = datetime.utcnow()
    db.commit()
    return {"status": "ok"}


@stats_router.get("/accuracy", response_model=AccuracyStatsResponse)
def accuracy_stats(market: str | None = None, db: Session = Depends(get_db)):
    """Calcola frequenza, percentuale di successo ed errore medio storico,
    filtrabile per market, sulla base delle previsioni per cui e' stato
    registrato un esito reale."""
    query = db.query(models.PredictionRecord)
    if market:
        query = query.filter(models.PredictionRecord.market == market)

    total = query.count()
    checked_query = query.filter(models.PredictionRecord.outcome_recorded.is_(True))
    checked = checked_query.count()

    hit_rate = None
    avg_error = None
    if checked > 0:
        hits = checked_query.filter(models.PredictionRecord.outcome_hit.is_(True)).count()
        hit_rate = hits / checked
        avg_error = checked_query.with_entities(
            func.avg(models.PredictionRecord.outcome_error_pct)
        ).scalar()

    return AccuracyStatsResponse(
        market=market,
        total_predictions=total,
        checked_predictions=checked,
        hit_rate=hit_rate,
        average_error_pct=float(avg_error) if avg_error is not None else None,
    )
