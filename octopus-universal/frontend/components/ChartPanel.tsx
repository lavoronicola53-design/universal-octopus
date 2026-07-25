"use client";

// components/ChartPanel.tsx
//
// Grafico a candele (lightweight-charts) con:
// - rendering delle candele storiche recuperate dal backend
// - selezione manuale del frattale: PRIMO click = inizio, SECONDO click =
//   fine (nessun riconoscimento automatico, come da requisito esplicito)
// - overlay dello scenario dominante come vere candele future (colore
//   distinto) e degli scenari secondari come linee tratteggiate
// - esportazione PNG/PDF dello screenshot del canvas

import { useEffect, useRef, useState, useCallback, forwardRef, useImperativeHandle } from "react";
import {
  createChart, ColorType, CrosshairMode, IChartApi, ISeriesApi,
  UTCTimestamp, SeriesMarker, Time,
} from "lightweight-charts";
import type { OHLCVBar, Scenario } from "@/lib/types";

interface ChartPanelProps {
  bars: OHLCVBar[];
  scenarios: Scenario[];
  selectionStart: number | null;
  selectionEnd: number | null;
  onPickPoint: (timestamp: number) => void;
}

export interface ChartPanelHandle {
  getCanvas: () => HTMLCanvasElement | null;
}

const SCENARIO_LINE_COLORS = ["#5C8FFF", "#D46CE8", "#6CE8C4", "#B98CFF"];

function toChartTime(epochSeconds: number): UTCTimestamp {
  return Math.floor(epochSeconds) as UTCTimestamp;
}

const ChartPanel = forwardRef<ChartPanelHandle, ChartPanelProps>(function ChartPanel(
  { bars, scenarios, selectionStart, selectionEnd, onPickPoint },
  ref,
) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const dominantSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const lineSeriesRefs = useRef<ISeriesApi<"Line">[]>([]);
  const [hoverInfo, setHoverInfo] = useState<string | null>(null);

  useImperativeHandle(ref, () => ({
    getCanvas: () => containerRef.current?.querySelector("canvas") ?? null,
  }));

  // --- inizializzazione chart (una sola volta) ---
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const chart = createChart(container, {
      layout: {
        background: { type: ColorType.Solid, color: "#0D0A16" },
        textColor: "#B7C0CE",
        fontFamily: "'IBM Plex Mono', monospace",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: "#171128" },
        horzLines: { color: "#171128" },
      },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: "#241A3D" },
      timeScale: { borderColor: "#241A3D", timeVisible: true, secondsVisible: false },
      autoSize: true,
    });

    const candleSeries = chart.addCandlestickSeries({
      upColor: "#3BD1A0",
      downColor: "#E15577",
      borderUpColor: "#3BD1A0",
      borderDownColor: "#E15577",
      wickUpColor: "#3BD1A0",
      wickDownColor: "#E15577",
    });

    const dominantSeries = chart.addCandlestickSeries({
      upColor: "#B98CFF",
      downColor: "#7E3BE8",
      borderUpColor: "#9D5CFF",
      borderDownColor: "#9D5CFF",
      wickUpColor: "#9D5CFF",
      wickDownColor: "#9D5CFF",
    });

    chart.subscribeClick((param) => {
      if (!param.time) return;
      onPickPoint(param.time as number);
    });

    chart.subscribeCrosshairMove((param) => {
      if (!param.time || !param.seriesData.size) {
        setHoverInfo(null);
        return;
      }
      const data = param.seriesData.get(candleSeries) as any;
      if (data) {
        setHoverInfo(
          `O ${data.open?.toFixed(2)}  H ${data.high?.toFixed(2)}  L ${data.low?.toFixed(2)}  C ${data.close?.toFixed(2)}`,
        );
      }
    });

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;
    dominantSeriesRef.current = dominantSeries;

    return () => {
      chart.remove();
      chartRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // --- aggiorna dati storici ---
  useEffect(() => {
    if (!candleSeriesRef.current) return;
    const data = bars
      .slice()
      .sort((a, b) => a.timestamp - b.timestamp)
      .map((b) => ({
        time: toChartTime(b.timestamp),
        open: b.open, high: b.high, low: b.low, close: b.close,
      }));
    candleSeriesRef.current.setData(data);
    chartRef.current?.timeScale().fitContent();
  }, [bars]);

  // --- marker di selezione (primo/secondo click) ---
  useEffect(() => {
    if (!candleSeriesRef.current) return;
    const markers: SeriesMarker<Time>[] = [];
    if (selectionStart) {
      markers.push({
        time: toChartTime(selectionStart), position: "belowBar",
        color: "#9D5CFF", shape: "arrowUp", text: "Inizio frattale",
      });
    }
    if (selectionEnd) {
      markers.push({
        time: toChartTime(selectionEnd), position: "aboveBar",
        color: "#9D5CFF", shape: "arrowDown", text: "Fine frattale",
      });
    }
    candleSeriesRef.current.setMarkers(markers);
  }, [selectionStart, selectionEnd]);

  // --- overlay scenario dominante (vere candele) + scenari secondari (linee) ---
  useEffect(() => {
    if (!chartRef.current || !dominantSeriesRef.current) return;

    // pulisce le linee scenario precedenti
    lineSeriesRefs.current.forEach((s) => chartRef.current?.removeSeries(s));
    lineSeriesRefs.current = [];

    const dominant = scenarios.find((s) => s.dominant);
    dominantSeriesRef.current.setData(
      (dominant?.candles ?? []).map((c) => ({
        time: toChartTime(c.timestamp), open: c.open, high: c.high, low: c.low, close: c.close,
      })),
    );

    const secondary = scenarios.filter((s) => !s.dominant).slice(0, 2);
    secondary.forEach((s, i) => {
      const line = chartRef.current!.addLineSeries({
        color: SCENARIO_LINE_COLORS[i % SCENARIO_LINE_COLORS.length],
        lineWidth: 2,
        lineStyle: 2, // dashed
        lastValueVisible: true,
        priceLineVisible: false,
        crosshairMarkerVisible: false,
        title: i === 0 ? "2ª proiezione" : "3ª proiezione",
      });
      line.setData(s.candles.map((c) => ({ time: toChartTime(c.timestamp), value: c.close })));
      lineSeriesRefs.current.push(line);
    });
  }, [scenarios]);

  return (
    <div className="relative w-full h-full">
      <div ref={containerRef} className="w-full h-full" />
      <div className="pointer-events-none absolute top-2 left-2 text-[11px] font-mono text-ink-300 bg-base-900/80 px-2 py-1 rounded">
        {hoverInfo ?? "Clicca due punti sul grafico per selezionare il frattale (inizio → fine)"}
      </div>
    </div>
  );
});

export default ChartPanel;
