"use client";

// components/ControlPanel.tsx
//
// Pannello operatore semplificato (come il software originale): l'operatore
// sceglie solo mercato, timeframe e il segmento frattale, poi preme il
// pulsante di calcolo. Nessuna opzione geometrica: il motore esegue
// direttamente la Trasformata di Fourier e restituisce la proiezione.

import { Timeframe, TIMEFRAMES, PredictionParams } from "@/lib/types";

interface ControlPanelProps {
  markets: string[];
  market: string;
  onMarketChange: (m: string) => void;

  timeframe: Timeframe;
  onTimeframeChange: (tf: Timeframe) => void;

  startDateTime: string; // valore input datetime-local
  endDateTime: string;
  onStartDateTimeChange: (v: string) => void;
  onEndDateTimeChange: (v: string) => void;

  params: PredictionParams;
  onParamsChange: (p: PredictionParams) => void;

  onPredict: () => void;
  predicting: boolean;
  canPredict: boolean;
  errorMessage?: string | null;
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-[11px] uppercase tracking-wide text-ink-500">{label}</span>
      {children}
    </label>
  );
}

const selectClass =
  "bg-base-800 border border-base-700 rounded-md px-2.5 py-1.5 text-sm text-ink-100 " +
  "focus:border-violet-500 focus:ring-0 outline-none transition-colors";

export default function ControlPanel(props: ControlPanelProps) {
  const {
    markets, market, onMarketChange,
    timeframe, onTimeframeChange,
    startDateTime, endDateTime, onStartDateTimeChange, onEndDateTimeChange,
    params, onParamsChange,
    onPredict, predicting, canPredict, errorMessage,
  } = props;

  return (
    <div className="flex flex-col gap-5 h-full overflow-y-auto pr-1">
      <section className="flex flex-col gap-3">
        <h2 className="text-xs font-semibold tracking-widest text-violet-400 uppercase">
          1 · Mercato &amp; timeframe
        </h2>
        <Field label="Strumento">
          <select className={selectClass} value={market} onChange={(e) => onMarketChange(e.target.value)}>
            {markets.map((m) => (
              <option key={m} value={m}>{m}</option>
            ))}
          </select>
        </Field>
        <Field label="Timeframe">
          <div className="grid grid-cols-4 gap-1.5">
            {TIMEFRAMES.map((tf) => (
              <button
                key={tf}
                onClick={() => onTimeframeChange(tf)}
                className={`text-xs py-1.5 rounded-md border transition-colors ${
                  tf === timeframe
                    ? "bg-violet-500/15 border-violet-500 text-violet-400"
                    : "bg-base-800 border-base-700 text-ink-300 hover:border-base-600"
                }`}
              >
                {tf}
              </button>
            ))}
          </div>
        </Field>
      </section>

      <hr className="border-base-700" />

      <section className="flex flex-col gap-3">
        <h2 className="text-xs font-semibold tracking-widest text-violet-400 uppercase">
          2 · Selezione temporale precisa
        </h2>
        <p className="text-[11px] text-ink-500 leading-relaxed">
          Puoi selezionare il frattale cliccando due punti sul grafico (inizio → fine),
          oppure impostare qui anno/mese/giorno/ora/minuto con precisione assoluta.
        </p>
        <Field label="Inizio frattale">
          <input
            type="datetime-local"
            className={selectClass}
            value={startDateTime}
            onChange={(e) => onStartDateTimeChange(e.target.value)}
          />
        </Field>
        <Field label="Fine frattale">
          <input
            type="datetime-local"
            className={selectClass}
            value={endDateTime}
            onChange={(e) => onEndDateTimeChange(e.target.value)}
          />
        </Field>
      </section>

      <div className="mt-auto pt-2 sticky bottom-0 bg-base-900/95 backdrop-blur">
        {errorMessage && (
          <p className="text-xs text-bear mb-2 leading-relaxed">{errorMessage}</p>
        )}
        <button
          onClick={onPredict}
          disabled={!canPredict || predicting}
          className="w-full py-2.5 rounded-md font-semibold text-sm tracking-wide
                     bg-violet-500 text-base-950 hover:bg-violet-400 transition-colors
                     disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {predicting ? "Calcolo trasformata in corso…" : "CALCOLA TRASFORMATA"}
        </button>
        <p className="text-[10px] text-ink-700 mt-2 leading-relaxed">
          Le proiezioni non costituiscono consulenza finanziaria né garanzia di risultati futuri.
        </p>
      </div>
    </div>
  );
}
