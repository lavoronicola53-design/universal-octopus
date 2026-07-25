// lib/api.ts
//
// Client API minimale verso il backend FastAPI. Le richieste passano da
// /api/* che Next.js inoltra al servizio backend (vedi next.config.js
// rewrites), cosi' nel browser non serve conoscere l'host del backend.

import {
  MarketListResponse, OHLCVBar, FractalSelection, PredictionParams,
  PredictionResponse, PatternDefinition,
} from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`Errore API ${res.status} su ${path}: ${body}`);
  }
  return res.json() as Promise<T>;
}

export function listMarkets(): Promise<MarketListResponse> {
  return request<MarketListResponse>("/api/market/list");
}

export function getOhlcv(
  market: string,
  timeframe: string,
  startTimestamp: number,
  endTimestamp: number,
): Promise<{ market: string; timeframe: string; bars: OHLCVBar[] }> {
  const params = new URLSearchParams({
    market, timeframe,
    start_timestamp: String(startTimestamp),
    end_timestamp: String(endTimestamp),
  });
  return request(`/api/market/ohlcv?${params.toString()}`);
}

export function predict(
  selection: FractalSelection,
  params: PredictionParams,
): Promise<PredictionResponse> {
  return request<PredictionResponse>("/api/prediction/predict", {
    method: "POST",
    body: JSON.stringify({ selection, params }),
  });
}

export function listPatterns(): Promise<PatternDefinition[]> {
  return request<PatternDefinition[]>("/api/patterns");
}

export function createPattern(payload: {
  label: string; min_candles: number; max_candles: number; description?: string;
}): Promise<PatternDefinition> {
  return request<PatternDefinition>("/api/patterns", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function recordOutcome(payload: {
  prediction_id: string; outcome_error_pct: number; outcome_hit: boolean;
}): Promise<{ status: string }> {
  return request("/api/stats/outcome", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export interface AccuracyStats {
  market?: string | null;
  total_predictions: number;
  checked_predictions: number;
  hit_rate?: number | null;
  average_error_pct?: number | null;
}

export function getAccuracyStats(market?: string): Promise<AccuracyStats> {
  const qs = market ? `?market=${encodeURIComponent(market)}` : "";
  return request<AccuracyStats>(`/api/stats/accuracy${qs}`);
}
