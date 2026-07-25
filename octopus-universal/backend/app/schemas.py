"""
schemas.py

Schemi Pydantic (request/response) per l'API FastAPI.
"""
from __future__ import annotations

from typing import Optional, Literal
from pydantic import BaseModel, Field, field_validator

Timeframe = Literal["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"]

ALLOWED_COMPONENTS = {10, 20, 50, 100, 200, 500, 1000}
ALLOWED_OVERTON = {50, 100, 200, 300, 500, 1000, 2000}


class MarketListResponse(BaseModel):
    markets: list[str]
    timeframes: list[str]


class OHLCVBar(BaseModel):
    timestamp: float
    open: float
    high: float
    low: float
    close: float
    volume: float


class OHLCVResponse(BaseModel):
    market: str
    timeframe: str
    bars: list[OHLCVBar]


class FractalSelection(BaseModel):
    """Il segmento selezionato manualmente dal trader sul grafico: primo
    click = inizio, secondo click = fine. Il backend NON individua da solo
    dove inizia/finisce il pattern."""
    market: str
    timeframe: Timeframe
    start_timestamp: float = Field(..., description="Timestamp epoch (s) del primo click")
    end_timestamp: float = Field(..., description="Timestamp epoch (s) del secondo click")
    pattern_id: Optional[str] = Field(None, description="ID pattern dal Book dei Frattali, se assegnato manualmente")

    @field_validator("end_timestamp")
    @classmethod
    def end_after_start(cls, v, info):
        start = info.data.get("start_timestamp")
        if start is not None and v <= start:
            raise ValueError("end_timestamp deve essere successivo a start_timestamp")
        return v


class PredictionParams(BaseModel):
    n_components: int = Field(100, description="Numero di componenti Fourier: 10/20/50/100/200/500/1000")
    horizon: int = Field(30, ge=1, le=500, description="Numero di candele future da generare")
    n_scenarios: int = Field(20, ge=1, le=100, description="Numero di scenari da generare (20-100)")
    overton_window: int = Field(200, description="Numero di barre storiche usate per l'analisi: 50/100/200/300/500/1000/2000")
    remove_outliers: bool = True
    apply_smoothing: bool = False
    vol_lookback: int = Field(20, ge=1, le=500)
    seed: int = 42
    enabled_transforms: list[str] = Field(
        default_factory=lambda: [
            "flip_v", "flip_h", "inversion", "temporal_scale",
            "amplitude_scale", "translation", "phase_rotation",
        ],
        description=(
            "Trasformazioni geometriche opzionali abilitate per la generazione "
            "scenari. Sottoinsieme di: flip_v, flip_h, inversion, temporal_scale, "
            "amplitude_scale, translation, phase_rotation."
        ),
    )

    @field_validator("n_components")
    @classmethod
    def validate_components(cls, v):
        if v not in ALLOWED_COMPONENTS:
            raise ValueError(f"n_components deve essere uno tra {sorted(ALLOWED_COMPONENTS)}")
        return v

    @field_validator("overton_window")
    @classmethod
    def validate_overton(cls, v):
        if v not in ALLOWED_OVERTON:
            raise ValueError(f"overton_window deve essere uno tra {sorted(ALLOWED_OVERTON)}")
        return v


class PredictionRequest(BaseModel):
    selection: FractalSelection
    params: PredictionParams = PredictionParams()


class ScenarioCandle(BaseModel):
    timestamp: float
    open: float
    high: float
    low: float
    close: float
    volume: Optional[float] = None
    synthetic: bool = True


class ScenarioMetricsResponse(BaseModel):
    reconstruction_error: float
    correlation: float
    spectral_coherence: float
    harmonic_continuity: float
    snr: float
    fractal_similarity: float
    multi_timeframe_stability: float


class ScenarioResponse(BaseModel):
    scenario_id: str
    transform: str
    score: float
    probability: float
    dominant: bool
    metrics: ScenarioMetricsResponse
    candles: list[ScenarioCandle]


class PredictionResponse(BaseModel):
    prediction_id: str
    market: str
    timeframe: str
    historical_bars: list[OHLCVBar]
    scenarios: list[ScenarioResponse]
    disclaimer: str = (
        "Questa proiezione e' generata tramite estrapolazione di Fourier su dati storici "
        "e non costituisce consulenza finanziaria ne' garanzia di risultati futuri. "
        "Il trading comporta il rischio di perdita del capitale."
    )


class PatternDefinitionSchema(BaseModel):
    id: str
    label: str
    min_candles: int
    max_candles: int
    description: Optional[str] = None
    is_custom: bool = False

    class Config:
        from_attributes = True


class PatternCreateRequest(BaseModel):
    label: str
    min_candles: int
    max_candles: int
    description: Optional[str] = None


class OutcomeUpdateRequest(BaseModel):
    prediction_id: str
    outcome_error_pct: float
    outcome_hit: bool


class AccuracyStatsResponse(BaseModel):
    market: Optional[str] = None
    total_predictions: int
    checked_predictions: int
    hit_rate: Optional[float] = None
    average_error_pct: Optional[float] = None
