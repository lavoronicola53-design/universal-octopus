"""
routers/prediction.py

Endpoint centrale "Predict": riceve la selezione manuale del frattale
(primo click / secondo click) + i parametri, recupera i dati storici
necessari (finestra di Overton), esegue l'intera pipeline multi-scenario
e salva la richiesta + gli scenari nel database statistico.
"""
from __future__ import annotations

import json
import time

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from ..schemas import (
    PredictionRequest, PredictionResponse, OHLCVBar,
    ScenarioResponse, ScenarioMetricsResponse, ScenarioCandle,
    MatchedPatternResponse,
)
from ..services.data_provider import get_provider, TIMEFRAME_SECONDS
from ..services.scenario_engine import run_prediction, PredictionRequestParams
from ..services.pattern_matching import match_pattern
from ..services.book_shapes import get_book_shapes
from ..database import get_db
from .. import models

router = APIRouter(prefix="/api/prediction", tags=["prediction"])

MAX_ELAPSED_WARNING_S = 2.0  # target di performance da specifica


@router.post("/predict", response_model=PredictionResponse)
def predict(payload: PredictionRequest, db: Session = Depends(get_db)) -> PredictionResponse:
    sel = payload.selection
    params_in = payload.params

    if sel.timeframe not in TIMEFRAME_SECONDS:
        raise HTTPException(400, f"Timeframe non supportato: {sel.timeframe}")

    dt = TIMEFRAME_SECONDS[sel.timeframe]
    overton_start = sel.start_timestamp - params_in.overton_window * dt

    provider = get_provider()
    try:
        series = provider.get_ohlcv(sel.market, sel.timeframe, overton_start, sel.end_timestamp)
        fractal = series.slice_between(sel.start_timestamp, sel.end_timestamp)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    engine_params = PredictionRequestParams(
        n_components=params_in.n_components,
        horizon=params_in.horizon,
        n_scenarios=params_in.n_scenarios,
        remove_outliers=params_in.remove_outliers,
        apply_smoothing=params_in.apply_smoothing,
        vol_lookback=params_in.vol_lookback,
        seed=params_in.seed,
        enabled_transforms=frozenset(params_in.enabled_transforms),
    )

    t0 = time.time()
    try:
        results, pre = run_prediction(
            fractal.timestamps, fractal.open, fractal.high, fractal.low,
            fractal.close, fractal.volume, engine_params,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    elapsed = time.time() - t0

    # --- persistenza nel database statistico ---
    record = models.PredictionRecord(
        market=sel.market,
        timeframe=sel.timeframe,
        fractal_start_ts=sel.start_timestamp,
        fractal_end_ts=sel.end_timestamp,
        pattern_id=sel.pattern_id,
        n_components=params_in.n_components,
        horizon=params_in.horizon,
        n_scenarios=params_in.n_scenarios,
        dominant_scenario_id=next(r.scenario_id for r in results if r.dominant),
        dominant_score=max(r.score for r in results),
    )
    db.add(record)
    db.flush()  # ottiene record.id senza commit definitivo

    for r in results:
        db.add(models.ScenarioRecord(
            prediction_id=record.id,
            scenario_label=r.scenario_id,
            transform_label=r.transform.label(),
            score=r.score,
            probability=r.probability,
            is_dominant=r.dominant,
            metrics_json=json.loads(json.dumps(r.to_dict(include_candles=False)["metrics"])),
            future_candles_json=[c.to_dict() for c in r.candles],
        ))
    db.commit()

    historical_bars = [OHLCVBar(**rec) for rec in fractal.to_records()]

    scenario_responses = [
        ScenarioResponse(
            scenario_id=r.scenario_id,
            transform=r.transform.label(),
            score=round(r.score, 4),
            probability=round(r.probability, 4),
            dominant=r.dominant,
            metrics=ScenarioMetricsResponse(**{
                "reconstruction_error": r.metrics.reconstruction_error,
                "correlation": r.metrics.correlation,
                "spectral_coherence": r.metrics.spectral_coherence,
                "harmonic_continuity": r.metrics.harmonic_continuity,
                "snr": r.metrics.snr,
                "fractal_similarity": r.metrics.fractal_similarity,
                "multi_timeframe_stability": r.metrics.multi_timeframe_stability,
            }),
            candles=[ScenarioCandle(**c.to_dict()) for c in r.candles],
        )
        for r in results
    ]

    # --- riconoscimento del pattern del Libro piu' simile per forma ---
    matched_response = None
    try:
        match = match_pattern(fractal.close, get_book_shapes())
        if match is not None:
            # recupera l'eventuale descrizione dal DB
            desc = None
            pat = db.query(models.PatternDefinition).filter_by(label=match.label).first()
            if pat is not None:
                desc = pat.description
            matched_response = MatchedPatternResponse(
                pattern_id=match.pattern_id,
                label=match.label,
                similarity=round(match.similarity, 4),
                similarity_pct=round(match.similarity * 100, 1),
                mirrored=match.mirrored,
                description=desc,
            )
    except Exception as exc:
        print(f"[WARN] pattern matching fallito: {exc}")

    response = PredictionResponse(
        prediction_id=record.id,
        market=sel.market,
        timeframe=sel.timeframe,
        historical_bars=historical_bars,
        scenarios=scenario_responses,
        matched_pattern=matched_response,
    )

    if elapsed > MAX_ELAPSED_WARNING_S:
        # non blocchiamo la risposta, ma logghiamo per osservabilita'/alerting
        print(f"[WARN] predict() ha impiegato {elapsed:.2f}s (target < {MAX_ELAPSED_WARNING_S}s)")

    return response
