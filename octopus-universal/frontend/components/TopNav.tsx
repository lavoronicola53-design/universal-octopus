"use client";

// components/TopNav.tsx

import SpectrumTicker from "./SpectrumTicker";

export default function TopNav() {
  return (
    <header className="h-14 shrink-0 border-b border-base-700 bg-base-900 flex items-center justify-between px-5">
      <div className="flex items-center gap-3">
        <div className="w-7 h-7 rounded bg-violet-500 flex items-center justify-center">
          <span className="text-base-950 font-bold text-sm">🐙</span>
        </div>
        <span className="font-semibold tracking-wide text-ink-100">Octopus Universal</span>
        <span className="text-[10px] text-ink-700 border border-base-700 rounded px-1.5 py-0.5 uppercase tracking-wider">
          Fourier Fractal Engine
        </span>
      </div>
      <SpectrumTicker bars={40} />
      <nav className="flex items-center gap-5 text-xs text-ink-500">
        <span className="text-ink-100 border-b-2 border-violet-500 pb-4 -mb-4">Prediction</span>
        <span className="hover:text-ink-100 cursor-pointer">Books</span>
        <span className="hover:text-ink-100 cursor-pointer">Training</span>
        <span className="hover:text-ink-100 cursor-pointer">Trading API</span>
      </nav>
    </header>
  );
}
