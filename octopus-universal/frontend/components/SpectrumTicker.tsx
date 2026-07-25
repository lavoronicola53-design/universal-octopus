"use client";

// components/SpectrumTicker.tsx
//
// Elemento "firma" del design: una barra ambient che rappresenta uno
// spettro di ampiezze in stile analizzatore di frequenze, richiamo diretto
// al cuore matematico del prodotto (FFT). Puramente decorativo/ambientale,
// rispetta prefers-reduced-motion tramite le regole in globals.css.

import { useEffect, useRef } from "react";

export default function SpectrumTicker({ bars = 48 }: { bars?: number }) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const children = Array.from(container.children) as HTMLDivElement[];
    let raf: number;
    let t = 0;

    const animate = () => {
      t += 0.02;
      children.forEach((el, i) => {
        // somma di poche armoniche per un movimento non periodico banale
        const v =
          0.5 +
          0.25 * Math.sin(t + i * 0.35) +
          0.15 * Math.sin(t * 1.9 + i * 0.7) +
          0.1 * Math.sin(t * 0.6 - i * 0.2);
        el.style.transform = `scaleY(${Math.max(0.08, Math.abs(v))})`;
      });
      raf = requestAnimationFrame(animate);
    };
    raf = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(raf);
  }, []);

  return (
    <div
      ref={containerRef}
      aria-hidden="true"
      className="flex items-end gap-[3px] h-6 opacity-70"
    >
      {Array.from({ length: bars }).map((_, i) => (
        <div
          key={i}
          className="w-[2px] h-full origin-bottom rounded-full bg-gradient-to-t from-violet-600 to-violet-400"
        />
      ))}
    </div>
  );
}
