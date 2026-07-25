import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Octopus Universal — Fourier Fractal Prediction",
  description: "Octopus Universal — proiezione di mercato tramite Trasformata di Fourier su frattali selezionati manualmente.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="it">
      <body className="font-sans antialiased">{children}</body>
    </html>
  );
}
