"""
scenario_engine.py

Orchestratore principale: dato un segmento frattale (OHLC storico
selezionato manualmente dal trader) e i parametri utente (numero di
componenti Fourier, orizzonte di proiezione, numero di scenari, quali
trasformazioni geometriche abilitare), produce N scenari futuri, ciascuno
con score/probabilita' e relative candele sintetiche.

Questo e' l'unico modulo che un router FastAPI deve chiamare per ottenere
il risultato completo di una richiesta "Predict".
"""
from __future__ import annotations

from dataclasses import dataclass, field
import numpy as np

from .preprocessing import preprocess_segment, PreprocessResult
from .fourier_engine import fourier_extrapolate, reconstruct
from .transforms import generate_transform_grid, apply_transform_spec, rotate_phase, TransformSpec
from .scoring import score_scenario, rank_scenarios, ScenarioMetrics
from .candle_synthesis import synthesize_future_candles, estimate_local_volatility, SyntheticCandle


@dataclass
class ScenarioResult:
    scenario_id: str
    transform: TransformSpec
    metrics: ScenarioMetrics
    score: float
    probability: float
    dominant: bool
    future_close_path: np.ndarray            # scala di prezzo reale
    candles: list[SyntheticCandle] = field(default_factory=list)

    def to_dict(self, include_candles: bool = True) -> dict:
        d = {
            "scenario_id": self.scenario_id,
            "transform": self.transform.label(),
            "score": round(self.score, 4),
            "probability": round(self.probability, 4),
            "dominant": self.dominant,
            "metrics": {
                "reconstruction_error": round(self.metrics.reconstruction_error, 4),
                "correlation": round(self.metrics.correlation, 4),
                "spectral_coherence": round(self.metrics.spectral_coherence, 4),
                "harmonic_continuity": round(self.metrics.harmonic_continuity, 4),
                "snr": round(self.metrics.snr, 4),
                "fractal_similarity": round(self.metrics.fractal_similarity, 4),
                "multi_timeframe_stability": round(self.metrics.multi_timeframe_stability, 4),
            },
        }
        if include_candles:
            d["candles"] = [c.to_dict() for c in self.candles]
        else:
            d["future_close_path"] = [round(float(v), 8) for v in self.future_close_path]
        return d


@dataclass
class PredictionRequestParams:
    n_components: int = 100          # 10/20/50/100/200/500/1000
    horizon: int = 30                # numero di candele future da generare
    n_scenarios: int = 20            # 20-100
    remove_outliers: bool = True
    apply_smoothing: bool = False
    vol_lookback: int = 20
    seed: int = 42
    enabled_transforms: frozenset[str] = field(default_factory=lambda: frozenset({
        "flip_v", "flip_h", "inversion", "temporal_scale",
        "amplitude_scale", "translation", "phase_rotation",
    }))


def run_prediction(
    timestamps: np.ndarray,
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    volume: np.ndarray | None,
    params: PredictionRequestParams,
) -> tuple[list[ScenarioResult], PreprocessResult]:
    """Esegue l'intera pipeline multi-scenario sul segmento frattale
    selezionato manualmente (`timestamps`..`volume` sono gli array OHLCV
    del SOLO segmento evidenziato dal trader tra primo e secondo click)."""

    pre = preprocess_segment(
        timestamps, close,
        remove_outliers_flag=params.remove_outliers,
        apply_smoothing=params.apply_smoothing,
    )

    reconstructed_hist, base_future, spectrum, selected_components = fourier_extrapolate(
        pre.processed, params.n_components, params.horizon,
    )

    transform_specs = generate_transform_grid(params.n_scenarios, enabled=set(params.enabled_transforms))

    # MODALITA' PULITA: se il trader non ha attivato trasformazioni
    # geometriche, generiamo comunque alcune varianti "legittime" della
    # stessa Trasformata di Fourier usando un numero diverso di componenti
    # (piu' componenti = piu' dettaglio, meno = piu' filtraggio del rumore,
    # come descritto nella teoria). Servono per mostrare la 2a/3a proiezione
    # piu' probabile come semplici linee, senza introdurre flip/inversioni.
    clean_mode = len(params.enabled_transforms) == 0
    clean_component_variants: list[int] = []
    if clean_mode:
        base = params.n_components
        allowed = [10, 20, 50, 100, 200, 500, 1000]
        # variante con meno dettaglio e una con piu' dettaglio, se disponibili
        lower = max([c for c in allowed if c < base], default=None)
        higher = min([c for c in allowed if c > base], default=None)
        clean_component_variants = [base] + [c for c in (lower, higher) if c is not None]
        # in modalita' pulita ignoriamo n_scenarios elevato: bastano 2-3 linee
        transform_specs = transform_specs[:1]

    local_vol_pct = estimate_local_volatility(high, low, close, lookback=params.vol_lookback)
    avg_volume = float(np.mean(volume)) if volume is not None and len(volume) else None
    last_close_real = float(pre.original[-1])
    last_timestamp = float(pre.timestamps[-1])

    raw_results: list[tuple[TransformSpec, ScenarioMetrics, np.ndarray]] = []

    # Prepara la lista di proiezioni-base da valutare. In modalita' pulita
    # sono le varianti a diverso numero di componenti Fourier; altrimenti e'
    # l'unica proiezione base a cui applicare le trasformazioni geometriche.
    base_projections: list[tuple[TransformSpec, np.ndarray]] = []
    if clean_mode:
        for k, n_comp in enumerate(clean_component_variants):
            _, fut_variant, _, _ = fourier_extrapolate(pre.processed, n_comp, params.horizon)
            label = "Proiezione Fourier" if k == 0 else f"Variante {n_comp} componenti"
            base_projections.append((TransformSpec(name=label), fut_variant))
    else:
        for spec in transform_specs:
            if spec.phase_shift_rad != 0.0:
                comps = rotate_phase(selected_components, spec.phase_shift_rad)
                fut = reconstruct(comps, params.horizon, offset=pre.meta["n_points"])
            else:
                fut = base_future.copy()
            base_projections.append((spec, fut))

    for spec, future_norm in base_projections:
        future_norm = apply_transform_spec(future_norm, spec)

        # denormalizza + riaggiunge il trend lineare esteso nel futuro
        future_detrended_scale = pre.denormalize(future_norm)
        future_real = pre.add_trend(future_detrended_scale, start_index=pre.meta["n_points"])

        # ANCORAGGIO: la proiezione deve ripartire dall'ultimo prezzo reale
        # osservato, non da dove "cade" la ricostruzione di Fourier. Senza
        # questo, tra l'ultima candela storica e la prima proiettata compare
        # un salto artificiale (candela iniziale "strana"). Riallineiamo il
        # primo punto della proiezione a last_close_real mantenendo la forma.
        if len(future_real) > 0:
            anchor_shift = last_close_real - future_real[0]
            future_real = future_real + anchor_shift

        metrics = score_scenario(
            observed_history=pre.original,
            reconstructed_history=pre.add_trend(pre.denormalize(reconstructed_hist), start_index=0),
            future_projection=future_real,
            energy_selected=spectrum.energy_selected,
            energy_total=spectrum.energy_total,
        )
        raw_results.append((spec, metrics, future_real))

    scores = [m.weighted_score() for _, m, _ in raw_results]
    probabilities = rank_scenarios(scores)
    dominant_idx = int(np.argmax(scores))

    results: list[ScenarioResult] = []
    for i, (spec, metrics, future_real) in enumerate(raw_results):
        seed_i = params.seed + i
        candles = synthesize_future_candles(
            close_path=future_real,
            last_close=last_close_real,
            dt_seconds=pre.dt_seconds,
            last_timestamp=last_timestamp,
            local_volatility_pct=local_vol_pct,
            avg_volume=avg_volume,
            seed=seed_i,
        )
        results.append(ScenarioResult(
            scenario_id=f"scenario_{i:03d}",
            transform=spec,
            metrics=metrics,
            score=scores[i],
            probability=float(probabilities[i]),
            dominant=(i == dominant_idx),
            future_close_path=future_real,
            candles=candles,
        ))

    results.sort(key=lambda r: r.probability, reverse=True)
    # rinomina scenari A..E (top 5) per l'output richiesto, mantenendo gli altri come extra
    labels = ["A", "B", "C", "D", "E"]
    for i, r in enumerate(results):
        if i < len(labels):
            r.scenario_id = f"Scenario {labels[i]}"
        else:
            r.scenario_id = f"Scenario {i+1}"

    return results, pre
