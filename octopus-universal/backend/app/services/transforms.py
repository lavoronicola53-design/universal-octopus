"""
transforms.py

Trasformazioni geometriche opzionali applicabili alla proiezione futura
generata dal motore di Fourier, per costruire scenari alternativi
(coerentemente con le operazioni descritte nella documentazione teorica:
flip verticale/orizzontale, centro di inversione, compressione/dilatazione
temporale e di ampiezza, traslazione, rotazione delle componenti di fase).

Ogni funzione e' pura (non modifica l'input) e opera su un array 1D che
rappresenta la proiezione futura (in unita' normalizzate, prima della
denormalizzazione a prezzo reale).
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
import numpy as np


def flip_vertical(series: np.ndarray) -> np.ndarray:
    """Specchia la serie rispetto al proprio valore medio (inversione di segno)."""
    mean = series.mean()
    return 2 * mean - series


def flip_horizontal(series: np.ndarray) -> np.ndarray:
    """Inverte l'ordine temporale della serie (specchio rispetto all'asse verticale)."""
    return series[::-1].copy()


def inversion_center(series: np.ndarray) -> np.ndarray:
    """Centro di inversione: composizione di flip verticale + flip
    orizzontale, equivalente a una rotazione di 180 gradi del pattern
    attorno al proprio centro (come descritto per la proiezione passato/
    futuro nel modello Evideon)."""
    return flip_vertical(flip_horizontal(series))


def compress_temporal(series: np.ndarray, factor: float) -> np.ndarray:
    """Comprime (factor < 1) o dilata (factor > 1) l'asse temporale via
    resampling per interpolazione lineare, mantenendo la lunghezza di
    output invariata (rimappa su una griglia di `len(series)` punti)."""
    n = len(series)
    src_idx = np.linspace(0, n - 1, max(2, int(round(n * factor))))
    src_idx = np.clip(src_idx, 0, n - 1)
    compressed = np.interp(src_idx, np.arange(n), series)
    # rimappa a lunghezza costante n (necessario per allineare con l'orizzonte richiesto)
    return np.interp(np.linspace(0, len(compressed) - 1, n), np.arange(len(compressed)), compressed)


def dilate_temporal(series: np.ndarray, factor: float) -> np.ndarray:
    """Alias esplicito di compress_temporal con factor > 1 (dilatazione)."""
    return compress_temporal(series, factor)


def compress_amplitude(series: np.ndarray, factor: float) -> np.ndarray:
    """Comprime (factor < 1) o dilata (factor > 1) l'ampiezza attorno alla
    media della serie."""
    mean = series.mean()
    return mean + (series - mean) * factor


def translate(series: np.ndarray, delta: float) -> np.ndarray:
    """Trasla verticalmente la serie di `delta` (in unita' normalizzate)."""
    return series + delta


def rotate_phase(components, phase_shift_rad: float):
    """Ruota la fase di tutte le componenti spettrali di un angolo fisso
    prima della ricostruzione. Ritorna una nuova lista di componenti (non
    modifica l'input)."""
    from .fourier_engine import SpectralComponent

    return [
        SpectralComponent(
            freq_index=c.freq_index,
            frequency=c.frequency,
            amplitude=c.amplitude,
            phase=c.phase + phase_shift_rad,
        )
        for c in components
    ]


@dataclass
class TransformSpec:
    """Descrive una combinazione di trasformazioni applicate a uno scenario."""
    name: str
    flip_v: bool = False
    flip_h: bool = False
    inversion: bool = False
    temporal_factor: float = 1.0
    amplitude_factor: float = 1.0
    translation: float = 0.0
    phase_shift_rad: float = 0.0

    def label(self) -> str:
        return self.name


def apply_transform_spec(series: np.ndarray, spec: TransformSpec) -> np.ndarray:
    out = series.copy()
    if spec.inversion:
        out = inversion_center(out)
    else:
        if spec.flip_v:
            out = flip_vertical(out)
        if spec.flip_h:
            out = flip_horizontal(out)
    if spec.temporal_factor != 1.0:
        out = compress_temporal(out, spec.temporal_factor)
    if spec.amplitude_factor != 1.0:
        out = compress_amplitude(out, spec.amplitude_factor)
    if spec.translation != 0.0:
        out = translate(out, spec.translation)
    return out


def generate_transform_grid(
    max_scenarios: int,
    enabled: set[str] | None = None,
) -> list[TransformSpec]:
    """Genera una griglia di combinazioni di trasformazioni (fino a
    `max_scenarios`), a partire dallo scenario "neutro" (nessuna
    trasformazione = proiezione Fourier pura) fino a combinazioni via via
    piu' aggressive. L'ordine e' deterministico per riproducibilita'.

    `enabled` e' un insieme di feature-flag opzionali che il trader puo'
    disattivare dalla UI (ognuna delle trasformazioni e' opzionale, come
    da specifica):
        "flip_v", "flip_h", "inversion",
        "temporal_scale", "amplitude_scale", "translation", "phase_rotation"
    Se None, sono tutte abilitate (comportamento di default/back-compat).
    """
    all_flags = {"flip_v", "flip_h", "inversion", "temporal_scale", "amplitude_scale", "translation", "phase_rotation"}
    enabled = all_flags if enabled is None else (enabled & all_flags)

    base_flags = [{"flip_v": False, "flip_h": False, "inversion": False}]
    if "flip_v" in enabled:
        base_flags.append({"flip_v": True, "flip_h": False, "inversion": False})
    if "flip_h" in enabled:
        base_flags.append({"flip_v": False, "flip_h": True, "inversion": False})
    if "inversion" in enabled:
        base_flags.append({"flip_v": False, "flip_h": False, "inversion": True})

    temporal_factors = [1.0, 0.85, 1.15, 0.7, 1.3] if "temporal_scale" in enabled else [1.0]
    amplitude_factors = [1.0, 0.85, 1.15, 0.7, 1.3] if "amplitude_scale" in enabled else [1.0]
    phase_shifts = [0.0, np.pi / 6, -np.pi / 6, np.pi / 3] if "phase_rotation" in enabled else [0.0]

    specs: list[TransformSpec] = []
    idx = 0
    for flags in base_flags:
        for tf in temporal_factors:
            for af in amplitude_factors:
                for ps in phase_shifts:
                    if len(specs) >= max_scenarios:
                        return specs
                    idx += 1
                    name = (
                        f"S{idx:03d}"
                        f"-{'INV' if flags['inversion'] else ('FV' if flags['flip_v'] else ('FH' if flags['flip_h'] else 'ID'))}"
                        f"-T{tf:.2f}-A{af:.2f}-P{ps:.2f}"
                    )
                    specs.append(TransformSpec(
                        name=name,
                        flip_v=flags["flip_v"],
                        flip_h=flags["flip_h"],
                        inversion=flags["inversion"],
                        temporal_factor=tf,
                        amplitude_factor=af,
                        phase_shift_rad=ps,
                    ))
    # se, con le combinazioni abilitate, non si raggiunge max_scenarios,
    # ripeti con piccole traslazioni verticali per diversificare (solo se
    # "translation" e' abilitata) invece di restituire meno scenari del richiesto
    if len(specs) < max_scenarios and "translation" in enabled:
        translations = [0.05, -0.05, 0.1, -0.1, 0.15, -0.15]
        base_specs = list(specs)
        t_i = 0
        while len(specs) < max_scenarios and base_specs:
            src = base_specs[t_i % len(base_specs)]
            t = translations[t_i % len(translations)]
            idx += 1
            specs.append(TransformSpec(
                name=f"S{idx:03d}-{src.name}-TR{t:+.2f}",
                flip_v=src.flip_v, flip_h=src.flip_h, inversion=src.inversion,
                temporal_factor=src.temporal_factor, amplitude_factor=src.amplitude_factor,
                translation=t, phase_shift_rad=src.phase_shift_rad,
            ))
            t_i += 1
    return specs
