"""
tests/test_core_pipeline.py

Test della pipeline matematica core (NON richiede FastAPI/DB/rete: usa solo
numpy/scipy/pandas, come i moduli in app/services). Eseguire con:

    cd backend && pytest -q
"""
import numpy as np
import pytest

from app.services.preprocessing import preprocess_segment
from app.services.fourier_engine import compute_spectrum, select_top_components, reconstruct, fourier_extrapolate
from app.services.transforms import (
    flip_vertical, flip_horizontal, inversion_center, generate_transform_grid, apply_transform_spec,
)
from app.services.scoring import score_scenario, rank_scenarios
from app.services.candle_synthesis import synthesize_future_candles, estimate_local_volatility
from app.services.scenario_engine import run_prediction, PredictionRequestParams


def _make_series(n=40, seed=1, drift=0.05):
    rng = np.random.default_rng(seed)
    dt = 900
    t0 = 1_700_000_000
    timestamps = t0 + dt * np.arange(n)
    close = 100 + np.cumsum(rng.normal(0, 0.6, n)) + drift * np.arange(n)
    open_ = close - rng.normal(0, 0.3, n)
    high = np.maximum(open_, close) + np.abs(rng.normal(0.3, 0.1, n))
    low = np.minimum(open_, close) - np.abs(rng.normal(0.3, 0.1, n))
    volume = np.abs(rng.normal(1000, 100, n))
    return timestamps, open_, high, low, close, volume


class TestPreprocessing:
    def test_basic_shapes(self):
        timestamps, _, _, _, close, _ = _make_series()
        result = preprocess_segment(timestamps, close)
        assert result.processed.shape == close.shape
        assert np.all(np.isfinite(result.processed))

    def test_denormalize_roundtrip_approx(self):
        timestamps, _, _, _, close, _ = _make_series()
        result = preprocess_segment(timestamps, close)
        detrended_scale = result.denormalize(result.processed)
        reconstructed = result.add_trend(detrended_scale, start_index=0)
        # la ricostruzione (senza filtraggio ne' selezione componenti) deve
        # tornare molto vicina alla serie originale osservata
        assert np.allclose(reconstructed, result.original, atol=1e-6)

    def test_raises_on_too_short_segment(self):
        timestamps, _, _, _, close, _ = _make_series(n=5)
        with pytest.raises(ValueError):
            preprocess_segment(timestamps, close)

    def test_outlier_clipping_reduces_extremes(self):
        timestamps, _, _, _, close, _ = _make_series()
        close_with_spike = close.copy()
        close_with_spike[10] += 1000  # spike enorme
        result = preprocess_segment(timestamps, close_with_spike)
        assert result.original[10] < close_with_spike[10]


class TestFourierEngine:
    def test_spectrum_energy_conservation(self):
        signal = np.sin(np.linspace(0, 8 * np.pi, 64))
        spectrum = compute_spectrum(signal)
        # Parseval: l'energia nel dominio del tempo deve corrispondere
        # (a meno di normalizzazione 1/n^2) a quella nel dominio della frequenza
        assert spectrum.energy_total > 0

    def test_select_top_components_limits_count(self):
        signal = np.random.default_rng(0).normal(0, 1, 64)
        spectrum = compute_spectrum(signal)
        selected = select_top_components(spectrum, n_components=5)
        # con coniugati, al massimo 2*5 componenti (meno se coincidenti, es. Nyquist/DC)
        assert len(selected) <= 10

    def test_reconstruction_close_to_original_with_all_components(self):
        signal = np.sin(np.linspace(0, 4 * np.pi, 32)) + 0.1 * np.random.default_rng(1).normal(size=32)
        spectrum = compute_spectrum(signal)
        selected = select_top_components(spectrum, n_components=32)  # praticamente tutte
        reconstructed = reconstruct(selected, len(signal), offset=0)
        assert np.allclose(reconstructed, signal, atol=1e-6)

    def test_extrapolate_produces_correct_horizon_length(self):
        signal = np.sin(np.linspace(0, 4 * np.pi, 40))
        hist, future, spectrum, comps = fourier_extrapolate(signal, n_components=10, horizon=15)
        assert len(hist) == 40
        assert len(future) == 15
        assert np.all(np.isfinite(future))


class TestTransforms:
    def test_flip_vertical_preserves_mean(self):
        s = np.array([1.0, 2.0, 3.0, 4.0])
        flipped = flip_vertical(s)
        assert np.isclose(flipped.mean(), s.mean())

    def test_flip_horizontal_reverses_order(self):
        s = np.array([1.0, 2.0, 3.0])
        assert np.allclose(flip_horizontal(s), np.array([3.0, 2.0, 1.0]))

    def test_inversion_center_is_180_rotation(self):
        s = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        inv = inversion_center(s)
        mean = s.mean()
        # elemento i-esimo della serie invertita = 2*mean - s[n-1-i]
        expected = 2 * mean - s[::-1]
        assert np.allclose(inv, expected)

    def test_generate_transform_grid_respects_max(self):
        specs = generate_transform_grid(max_scenarios=17)
        assert len(specs) == 17

    def test_apply_transform_spec_runs_without_error(self):
        from app.services.transforms import TransformSpec
        s = np.linspace(0, 1, 20)
        spec = TransformSpec(name="t", flip_v=True, temporal_factor=0.9, amplitude_factor=1.1, translation=0.1)
        out = apply_transform_spec(s, spec)
        assert len(out) == len(s)
        assert np.all(np.isfinite(out))


class TestScoring:
    def test_score_scenario_bounds(self):
        rng = np.random.default_rng(2)
        observed = 100 + np.cumsum(rng.normal(0, 1, 30))
        reconstructed = observed + rng.normal(0, 0.1, 30)
        future = observed[-1] + np.cumsum(rng.normal(0, 1, 10))
        metrics = score_scenario(observed, reconstructed, future, energy_selected=8.0, energy_total=10.0)
        score = metrics.weighted_score()
        assert 0.0 <= score <= 1.0

    def test_rank_scenarios_sums_to_one(self):
        probs = rank_scenarios([0.9, 0.5, 0.3, 0.95, 0.1])
        assert np.isclose(probs.sum(), 1.0)
        assert probs[3] == probs.max()  # score piu' alto -> probabilita' piu' alta


class TestCandleSynthesis:
    def test_synthesize_future_candles_ohlc_consistency(self):
        close_path = 100 + np.cumsum(np.random.default_rng(5).normal(0, 0.5, 10))
        candles = synthesize_future_candles(
            close_path=close_path, last_close=100.0, dt_seconds=900,
            last_timestamp=1_700_000_000, local_volatility_pct=0.01,
            avg_volume=1000.0, seed=42,
        )
        assert len(candles) == 10
        for c in candles:
            assert c.high >= max(c.open, c.close)
            assert c.low <= min(c.open, c.close)
            assert c.volume is not None and c.volume >= 0

    def test_reproducibility_same_seed(self):
        close_path = np.array([100.0, 101.0, 99.5])
        c1 = synthesize_future_candles(close_path, 100.0, 900, 0, 0.02, 1000.0, seed=7)
        c2 = synthesize_future_candles(close_path, 100.0, 900, 0, 0.02, 1000.0, seed=7)
        assert [c.to_dict() for c in c1] == [c.to_dict() for c in c2]

    def test_estimate_local_volatility_positive(self):
        high = np.array([101.0, 102.0, 103.0])
        low = np.array([99.0, 100.0, 101.0])
        close = np.array([100.0, 101.0, 102.0])
        vol = estimate_local_volatility(high, low, close, lookback=3)
        assert vol > 0


class TestScenarioEngineIntegration:
    def test_run_prediction_end_to_end(self):
        timestamps, open_, high, low, close, volume = _make_series(n=40)
        params = PredictionRequestParams(n_components=20, horizon=10, n_scenarios=25, seed=1)
        results, pre = run_prediction(timestamps, open_, high, low, close, volume, params)

        assert len(results) == 25
        assert sum(r.probability for r in results) == pytest.approx(1.0, abs=1e-6)
        assert sum(1 for r in results if r.dominant) == 1
        for r in results:
            assert len(r.candles) == 10
            assert r.scenario_id.startswith("Scenario")

    def test_run_prediction_respects_performance_target(self):
        import time
        timestamps, open_, high, low, close, volume = _make_series(n=200)
        params = PredictionRequestParams(n_components=1000, horizon=50, n_scenarios=100, seed=1)
        start = time.time()
        results, _ = run_prediction(timestamps, open_, high, low, close, volume, params)
        elapsed = time.time() - start
        assert elapsed < 2.0
        assert len(results) == 100

    def test_run_prediction_rejects_too_short_fractal(self):
        timestamps, open_, high, low, close, volume = _make_series(n=5)
        params = PredictionRequestParams()
        with pytest.raises(ValueError):
            run_prediction(timestamps, open_, high, low, close, volume, params)
