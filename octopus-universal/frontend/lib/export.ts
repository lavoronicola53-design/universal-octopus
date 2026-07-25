// lib/export.ts
//
// Funzioni di esportazione richieste dalle specifiche: PNG, PDF, CSV, JSON.
// PNG: usa lo screenshot nativo di lightweight-charts (chart.takeScreenshot()).
// PDF: incapsula lo screenshot PNG in un PDF (jsPDF), su una pagina singola.
// CSV/JSON: serializzano scenari e candele storiche/proiettate.

import { jsPDF } from "jspdf";
import type { PredictionResponse } from "./types";

export function downloadBlob(filename: string, content: string, mime: string) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export function exportChartPNG(canvas: HTMLCanvasElement, filename = "octopus_universal_chart.png") {
  canvas.toBlob((blob) => {
    if (!blob) return;
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }, "image/png");
}

export function exportChartPDF(canvas: HTMLCanvasElement, filename = "octopus_universal_chart.pdf") {
  const imgData = canvas.toDataURL("image/png");
  const orientation = canvas.width >= canvas.height ? "landscape" : "portrait";
  const pdf = new jsPDF({ orientation, unit: "px", format: [canvas.width, canvas.height] });
  pdf.addImage(imgData, "PNG", 0, 0, canvas.width, canvas.height);
  pdf.save(filename);
}

export function exportPredictionCSV(prediction: PredictionResponse, filename = "octopus_universal_prediction.csv") {
  const rows: string[] = [];
  rows.push("section,scenario_id,timestamp,open,high,low,close,volume,synthetic");
  for (const bar of prediction.historical_bars) {
    rows.push(`historical,,${bar.timestamp},${bar.open},${bar.high},${bar.low},${bar.close},${bar.volume},false`);
  }
  for (const scenario of prediction.scenarios) {
    for (const candle of scenario.candles) {
      rows.push(
        `projection,${scenario.scenario_id},${candle.timestamp},${candle.open},${candle.high},${candle.low},${candle.close},${candle.volume ?? ""},${candle.synthetic}`,
      );
    }
  }
  downloadBlob(filename, rows.join("\n"), "text/csv");
}

export function exportPredictionJSON(prediction: PredictionResponse, filename = "octopus_universal_prediction.json") {
  downloadBlob(filename, JSON.stringify(prediction, null, 2), "application/json");
}
