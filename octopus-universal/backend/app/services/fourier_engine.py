"""
fourier_engine.py

Analisi spettrale reale (numpy.fft) del segmento frattale pre-processato e
generazione dell'estrapolazione futura per "continuazione di Fourier"
(Fourier extrapolation): la serie storica viene scomposta in armoniche
(frequenza, ampiezza, fase); si selezionano le N componenti piu' energetiche
(parametro "Fourier Components" richiesto dall'utente: 10/20/50/100/200/
500/1000) e si prolunga la somma di sinusoidi oltre la fine della finestra
storica.

NOTA METODOLOGICA (va riportata anche in UI): la Trasformata di Fourier
assume implicitamente periodicita' del segnale. Estrapolare oltre i dati
osservati equivale a ipotizzare che il pattern si ripeta ciclicamente: e'
una tecnica di proiezione geometrica, non un modello predittivo validato
statisticamente. Il modulo di scoring (scoring.py) fornisce metriche
oggettive di qualita' della ricostruzione, ma nessuna di esse costituisce
una garanzia di accuratezza predittiva futura.
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np


@dataclass
class SpectralComponent:
    freq_index: int         # indice della frequenza nell'array FFT
    frequency: float        # frequenza (cicli per campione)
    amplitude: float        # |coefficiente| (ampiezza)
    phase: float             # fase (radianti)


@dataclass
class SpectrumResult:
    fft_full: np.ndarray               # spettro completo (complesso), non filtrato
    n_samples: int
    components: list[SpectralComponent]   # componenti ordinate per energia decrescente
    energy_total: float
    energy_selected: float


def compute_spectrum(signal: np.ndarray) -> SpectrumResult:
    """Esegue la FFT reale sul segnale (gia' pre-processato: detrended e
    normalizzato) ed estrae tutte le componenti spettrali ordinate per
    energia (ampiezza^2) decrescente."""
    n = len(signal)
    spectrum = np.fft.fft(signal)
    freqs = np.fft.fftfreq(n)

    amplitudes = np.abs(spectrum) / n
    phases = np.angle(spectrum)
    energy = amplitudes ** 2
    energy_total = float(energy.sum())

    order = np.argsort(energy)[::-1]

    components = [
        SpectralComponent(
            freq_index=int(i),
            frequency=float(freqs[i]),
            amplitude=float(amplitudes[i]),
            phase=float(phases[i]),
        )
        for i in order
    ]

    return SpectrumResult(
        fft_full=spectrum,
        n_samples=n,
        components=components,
        energy_total=energy_total if energy_total > 0 else 1e-12,
        energy_selected=0.0,
    )


def select_top_components(spectrum: SpectrumResult, n_components: int) -> list[SpectralComponent]:
    """Seleziona le N componenti piu' energetiche. Le componenti sono
    conservate a coppie coniugate (freq e -freq) perche' il segnale di
    ingresso e' reale: numpy.fft.fft su input reale produce uno spettro
    hermitiano simmetrico, quindi selezioniamo l'indice piu' energetico e
    aggiungiamo automaticamente il suo coniugato se non gia' incluso."""
    n = spectrum.n_samples
    selected: dict[int, SpectralComponent] = {}
    for comp in spectrum.components:
        if len(selected) >= n_components * 2:  # *2 perche' includiamo i coniugati
            break
        selected[comp.freq_index] = comp
        conj_index = (-comp.freq_index) % n
        if conj_index not in selected:
            conj_comp = SpectralComponent(
                freq_index=conj_index,
                frequency=-comp.frequency,
                amplitude=comp.amplitude,
                phase=-comp.phase,
            )
            selected[conj_index] = conj_comp

    energy_selected = sum(c.amplitude ** 2 for c in selected.values())
    spectrum.energy_selected = float(energy_selected)
    return list(selected.values())


def reconstruct(components: list[SpectralComponent], n_samples: int, offset: int = 0) -> np.ndarray:
    """Ricostruisce/estrapola la serie temporale a partire da un set di
    componenti spettrali (frequenza, ampiezza, fase), valutando la somma di
    sinusoidi su `n_samples` punti a partire dall'indice `offset` (offset=0
    ricostruisce la storia; offset=len(storia) estrapola il futuro).

    x[t] = sum_k A_k * cos(2*pi*f_k*(t+offset) + phi_k)   [forma reale equivalente]

    Nota: usiamo la formulazione con esponenziale complesso coerente con la
    convenzione di numpy.fft (X_k = A_k * n * exp(i*phi_k)), che per
    costruzione somma correttamente le coppie coniugate producendo un
    risultato reale.
    """
    t = np.arange(offset, offset + n_samples)
    signal = np.zeros(n_samples, dtype=np.complex128)
    for comp in components:
        angle = 2.0 * np.pi * comp.frequency * t + comp.phase
        signal += comp.amplitude * np.exp(1j * angle)
    return np.real(signal)


def fourier_extrapolate(
    processed_signal: np.ndarray,
    n_components: int,
    horizon: int,
) -> tuple[np.ndarray, np.ndarray, SpectrumResult, list[SpectralComponent]]:
    """Pipeline completa: FFT -> selezione top-N componenti -> ricostruzione
    storica (per validazione/scoring) -> estrapolazione futura di
    `horizon` campioni.

    Ritorna: (storia_ricostruita, proiezione_futura, spectrum_completo, componenti_selezionate)
    """
    n = len(processed_signal)
    spectrum = compute_spectrum(processed_signal)
    selected = select_top_components(spectrum, n_components)

    reconstructed_history = reconstruct(selected, n, offset=0)
    future_projection = reconstruct(selected, horizon, offset=n)

    return reconstructed_history, future_projection, spectrum, selected
