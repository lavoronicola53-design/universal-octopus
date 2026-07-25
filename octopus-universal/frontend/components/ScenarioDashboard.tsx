"use client";

// components/ScenarioDashboard.tsx
//
// Mostra gli scenari generati (Scenario A..E + eventuali extra) ordinati
// per probabilita' (step 7 del flusso), con le metriche di scoring e i
// pulsanti di esportazione (step "Esportazione": PNG/PDF/CSV/JSON).

import type { PredictionResponse } from "@/lib/types";
import { exportPredictionCSV, exportPredictionJSON, exportChartPNG, exportChartPDF } from "@/lib/export";

interface ScenarioDashboardProps {
  prediction: PredictionResponse | null;
  chartCanvas: HTMLCanvasElement | null;
}

function MetricBar({ label, value }: { label: string; value: number }) {
  const pct = Math.max(0, Math.min(1, value)) * 100;
  return (
    <div className="flex items-center gap-2 text-[11px]">
      <span className="w-40 text-ink-500 shrink-0">{label}</span>
      <div className="flex-1 h-1.5 rounded-full bg-base-700 overflow-hidden">
        <div className="h-full bg-violet-500/80" style={{ width: `${pct}%` }} />
      </div>
      <span className="w-10 text-right text-ink-300 tabular-nums">{value.toFixed(2)}</span>
    </div>
  );
}

export default function ScenarioDashboard({ prediction, chartCanvas }: ScenarioDashboardProps) {
  if (!prediction) {
    return (
      <div className="h-full flex items-center justify-center text-sm text-ink-700">
        Seleziona un frattale e premi PREDICT per generare gli scenari.
      </div>
    );
  }

  const dominant = prediction.scenarios.find((s) => s.dominant) ?? prediction.scenarios[0];

  return (
    <div className="flex flex-col h-full gap-4 overflow-y-auto pr-1">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xs font-semibold tracking-widest text-violet-400 uppercase">
            Scenari proiettati
          </h2>
          <p className="text-[11px] text-ink-500">
            {prediction.market} · {prediction.timeframe} · {prediction.scenarios.length} scenari
          </p>
        </div>
        <div className="flex gap-1.5">
          <button
            className="text-[11px] px-2 py-1 rounded bg-base-800 border border-base-700 hover:border-violet-500 text-ink-300"
            onClick={() => chartCanvas && exportChartPNG(chartCanvas)}
          >
            PNG
          </button>
          <button
            className="text-[11px] px-2 py-1 rounded bg-base-800 border border-base-700 hover:border-violet-500 text-ink-300"
            onClick={() => chartCanvas && exportChartPDF(chartCanvas)}
          >
            PDF
          </button>
          <button
            className="text-[11px] px-2 py-1 rounded bg-base-800 border border-base-700 hover:border-violet-500 text-ink-300"
            onClick={() => exportPredictionCSV(prediction)}
          >
            CSV
          </button>
          <button
            className="text-[11px] px-2 py-1 rounded bg-base-800 border border-base-700 hover:border-violet-500 text-ink-300"
            onClick={() => exportPredictionJSON(prediction)}
          >
            JSON
          </button>
        </div>
      </div>

      {prediction.matched_pattern && (
        <div className="rounded-lg border border-violet-500/40 bg-violet-500/5 p-3 flex flex-col gap-1.5">
          <div className="flex items-center justify-between">
            <span className="text-[11px] uppercase tracking-wide text-ink-500">
              Frattale del Libro più simile
            </span>
            <span className="text-sm font-mono text-violet-400">
              {prediction.matched_pattern.similarity_pct.toFixed(1)}%
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-base font-semibold text-ink-100">
              {prediction.matched_pattern.label}
            </span>
            {prediction.matched_pattern.mirrored && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-base-700 text-ink-300">
                speculare
              </span>
            )}
          </div>
          {prediction.matched_pattern.description && (
            <p className="text-[11px] text-ink-500 leading-relaxed">
              {prediction.matched_pattern.description}
            </p>
          )}
          <p className="text-[10px] text-ink-700 leading-relaxed">
            Confronto per struttura geometrica (indipendente dal numero di candele).
          </p>
        </div>
      )}

      {dominant && (
        <div className="rounded-lg border border-violet-500/40 bg-violet-500/5 p-3 flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <span className="text-sm font-semibold text-violet-400">
              Scenario dominante · {dominant.scenario_id}
            </span>
            <span className="text-sm font-mono text-violet-400">
              {(dominant.probability * 100).toFixed(1)}%
            </span>
          </div>
          <div className="grid grid-cols-2 gap-x-4 gap-y-1.5">
            <MetricBar label="Correlazione" value={Math.max(0, dominant.metrics.correlation)} />
            <MetricBar label="Coerenza spettrale" value={dominant.metrics.spectral_coherence} />
            <MetricBar label="Continuità armonica" value={dominant.metrics.harmonic_continuity} />
            <MetricBar label="Similarità frattale" value={dominant.metrics.fractal_similarity} />
          </div>
        </div>
      )}

      <div className="flex flex-col gap-2">
        {prediction.scenarios.map((s, i) => (
          <div
            key={s.scenario_id}
            className={`rounded-md border px-3 py-2 flex items-center justify-between text-xs ${
              s.dominant ? "border-violet-500/50 bg-violet-500/5" : "border-base-700 bg-base-850"
            }`}
          >
            <div className="flex items-center gap-3">
              <span
                className="w-1.5 h-1.5 rounded-full shrink-0"
                style={{ backgroundColor: s.dominant ? "#9D5CFF" : "#564B70" }}
              />
              <span className="font-medium text-ink-100">{s.scenario_id}</span>
              <span className="text-ink-700 font-mono text-[10px]">{s.transform}</span>
            </div>
            <div className="flex items-center gap-3 font-mono">
              <span className="text-ink-500">score {s.score.toFixed(3)}</span>
              <span className="text-violet-400 w-14 text-right">{(s.probability * 100).toFixed(1)}%</span>
            </div>
          </div>
        ))}
      </div>

      <p className="text-[10px] text-ink-700 leading-relaxed border-t border-base-700 pt-3">
        {prediction.disclaimer}
      </p>
    </div>
  );
}
