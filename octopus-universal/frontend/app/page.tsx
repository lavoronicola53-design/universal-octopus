"use client";

// app/page.tsx
//
// Pagina unica dell'applicazione: collega ControlPanel, ChartPanel e
// ScenarioDashboard, gestendo lo stato di selezione mercato/timeframe,
// selezione manuale del frattale (due click) e la chiamata all'endpoint
// /api/prediction/predict.

import { useEffect, useRef, useState, useCallback } from "react";
import TopNav from "@/components/TopNav";
import ControlPanel from "@/components/ControlPanel";
import ChartPanel, { ChartPanelHandle } from "@/components/ChartPanel";
import ScenarioDashboard from "@/components/ScenarioDashboard";
import { listMarkets, getOhlcv, predict } from "@/lib/api";
import { epochToDatetimeLocal, datetimeLocalToEpoch } from "@/lib/datetime";
import {
  Timeframe, OHLCVBar, PredictionParams, DEFAULT_PREDICTION_PARAMS, PredictionResponse,
} from "@/lib/types";

const DEFAULT_TIMEFRAME: Timeframe = "15m";

export default function HomePage() {
  const chartRef = useRef<ChartPanelHandle>(null);

  const [markets, setMarkets] = useState<string[]>([]);
  const [market, setMarket] = useState<string>("BTC/USDT");
  const [timeframe, setTimeframe] = useState<Timeframe>(DEFAULT_TIMEFRAME);

  const [bars, setBars] = useState<OHLCVBar[]>([]);
  const [loadingBars, setLoadingBars] = useState(false);

  const [selectionStart, setSelectionStart] = useState<number | null>(null);
  const [selectionEnd, setSelectionEnd] = useState<number | null>(null);

  const [params, setParams] = useState<PredictionParams>(DEFAULT_PREDICTION_PARAMS);
  // Modalità operatore (come il software originale): nessuna trasformazione
  // geometrica. Il motore esegue direttamente la Trasformata di Fourier e
  // restituisce la proiezione. L'operatore non sceglie nulla oltre a
  // mercato, timeframe e segmento frattale.

  const [prediction, setPrediction] = useState<PredictionResponse | null>(null);
  const [predicting, setPredicting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // --- carica elenco mercati all'avvio ---
  useEffect(() => {
    listMarkets()
      .then((res) => {
        setMarkets(res.markets);
        if (res.markets.length && !res.markets.includes(market)) {
          setMarket(res.markets[0]);
        }
      })
      .catch(() => setErrorMessage("Impossibile contattare il backend (/api/market/list)."));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // --- carica dati OHLCV quando cambia mercato/timeframe ---
  const reloadBars = useCallback(async () => {
    setLoadingBars(true);
    setErrorMessage(null);
    try {
      const now = Math.floor(Date.now() / 1000);
      const secondsPerBar = { "1m": 60, "5m": 300, "15m": 900, "30m": 1800, "1h": 3600, "4h": 14400, "1d": 86400, "1w": 604800 }[timeframe];
      const start = now - secondsPerBar * 400; // ~400 barre di storico visibili
      const res = await getOhlcv(market, timeframe, start, now);
      setBars(res.bars);
    } catch (e: any) {
      setErrorMessage(e.message ?? "Errore nel caricamento dei dati OHLCV");
    } finally {
      setLoadingBars(false);
    }
  }, [market, timeframe]);

  useEffect(() => {
    reloadBars();
    setSelectionStart(null);
    setSelectionEnd(null);
    setPrediction(null);
  }, [reloadBars]);

  // --- selezione manuale del frattale a due click sul grafico ---
  const handlePickPoint = useCallback((timestamp: number) => {
    setSelectionStart((prevStart) => {
      if (prevStart === null) {
        setSelectionEnd(null);
        return timestamp;
      }
      // Se c'e' gia' un punto di inizio: questo click chiude la selezione
      setSelectionEnd((prevEnd) => {
        if (prevEnd === null) {
          return timestamp > prevStart ? timestamp : prevStart;
        }
        return prevEnd;
      });
      if (timestamp <= prevStart) {
        // secondo click precede il primo: reset e usa questo come nuovo inizio
        return timestamp;
      }
      return prevStart;
    });
  }, []);

  // sincronizza gli input datetime-local con la selezione da grafico
  const startDateTime = selectionStart ? epochToDatetimeLocal(selectionStart) : "";
  const endDateTime = selectionEnd ? epochToDatetimeLocal(selectionEnd) : "";

  const handleStartDateTimeChange = (v: string) => {
    const epoch = datetimeLocalToEpoch(v);
    setSelectionStart(epoch);
  };
  const handleEndDateTimeChange = (v: string) => {
    const epoch = datetimeLocalToEpoch(v);
    setSelectionEnd(epoch);
  };

  const canPredict = selectionStart !== null && selectionEnd !== null && selectionEnd > selectionStart;

  const handlePredict = async () => {
    if (!canPredict || selectionStart === null || selectionEnd === null) return;
    setPredicting(true);
    setErrorMessage(null);
    try {
      const result = await predict(
        {
          market, timeframe,
          start_timestamp: selectionStart,
          end_timestamp: selectionEnd,
        },
        // enabled_transforms vuoto: solo Trasformata di Fourier, nessuna
        // variante geometrica scelta dall'operatore.
        { ...params, enabled_transforms: [] } as any,
      );
      setPrediction(result);
    } catch (e: any) {
      setErrorMessage(e.message ?? "Errore durante la generazione della previsione");
      setPrediction(null);
    } finally {
      setPredicting(false);
    }
  };

  return (
    <div className="h-screen flex flex-col bg-base-950">
      <TopNav />
      <div className="flex-1 grid grid-cols-[280px_1fr_360px] min-h-0">
        <aside className="border-r border-base-700 bg-base-900 px-4 py-4">
          <ControlPanel
            markets={markets}
            market={market}
            onMarketChange={setMarket}
            timeframe={timeframe}
            onTimeframeChange={setTimeframe}
            startDateTime={startDateTime}
            endDateTime={endDateTime}
            onStartDateTimeChange={handleStartDateTimeChange}
            onEndDateTimeChange={handleEndDateTimeChange}
            params={params}
            onParamsChange={setParams}
            onPredict={handlePredict}
            predicting={predicting}
            canPredict={canPredict}
            errorMessage={errorMessage}
          />
        </aside>

        <main className="relative min-w-0">
          {loadingBars && (
            <div className="absolute inset-0 z-10 flex items-center justify-center bg-base-950/60 text-ink-500 text-sm">
              Caricamento dati di mercato…
            </div>
          )}
          <ChartPanel
            ref={chartRef}
            bars={bars}
            scenarios={prediction?.scenarios ?? []}
            selectionStart={selectionStart}
            selectionEnd={selectionEnd}
            onPickPoint={handlePickPoint}
          />
        </main>

        <aside className="border-l border-base-700 bg-base-900 px-4 py-4">
          <ScenarioDashboard prediction={prediction} chartCanvas={chartRef.current?.getCanvas() ?? null} />
        </aside>
      </div>
    </div>
  );
}
