// lib/types.ts
//
// Tipi condivisi tra i componenti del frontend, allineati agli schemi
// Pydantic del backend (app/schemas.py).

export type Timeframe = "1m" | "5m" | "15m" | "30m" | "1h" | "4h" | "1d" | "1w";

export const TIMEFRAMES: Timeframe[] = ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"];

export const FOURIER_COMPONENT_OPTIONS = [10, 20, 50, 100, 200, 500, 1000] as const;
export const OVERTON_WINDOW_OPTIONS = [50, 100, 200, 300, 500, 1000, 2000] as const;

export interface OHLCVBar {
  timestamp: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface MarketListResponse {
  markets: string[];
  timeframes: string[];
}

export interface FractalSelection {
  market: string;
  timeframe: Timeframe;
  start_timestamp: number;
  end_timestamp: number;
  pattern_id?: string | null;
}

export interface PredictionParams {
  n_components: number;
  horizon: number;
  n_scenarios: number;
  overton_window: number;
  remove_outliers: boolean;
  apply_smoothing: boolean;
  vol_lookback: number;
  seed: number;
}

export const DEFAULT_PREDICTION_PARAMS: PredictionParams = {
  n_components: 100,
  horizon: 30,
  n_scenarios: 20,
  overton_window: 200,
  remove_outliers: true,
  apply_smoothing: false,
  vol_lookback: 20,
  seed: 42,
};

export interface ScenarioCandle extends OHLCVBar {
  synthetic: boolean;
}

export interface ScenarioMetrics {
  reconstruction_error: number;
  correlation: number;
  spectral_coherence: number;
  harmonic_continuity: number;
  snr: number;
  fractal_similarity: number;
  multi_timeframe_stability: number;
}

export interface Scenario {
  scenario_id: string;
  transform: string;
  score: number;
  probability: number;
  dominant: boolean;
  metrics: ScenarioMetrics;
  candles: ScenarioCandle[];
}

export interface PredictionResponse {
  prediction_id: string;
  market: string;
  timeframe: string;
  historical_bars: OHLCVBar[];
  scenarios: Scenario[];
  disclaimer: string;
}

export interface PatternDefinition {
  id: string;
  label: string;
  min_candles: number;
  max_candles: number;
  description?: string | null;
  is_custom: boolean;
}
