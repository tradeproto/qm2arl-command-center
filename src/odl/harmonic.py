"""
Harmonic resonance layer for the Omni-Dimensional Ledger.

Turns raw multi-dimensional TIME-SERIES signals — vibration/frequency,
biometrics, ecology, economics, weather, quantum-sensory telemetry — into a
single **Harmony Score H ∈ [0,1]** plus a resonant/dissonant diagnosis, using
real signal processing and linear algebra (no mysticism):

  1. SIGNAL TENSOR — signals are stacked into a rank-2 tensor S (n_signals × T),
     z-scored. (Higher-rank tensors over space/time collapse to this via the
     same contraction; rank-2 is the operational case.)

  2. SPECTRAL DECOMPOSITION — FFT of each signal gives its dominant frequency,
     amplitude, and phase (the "vibration/frequency" dimension made concrete).

  3. COUPLING EIGEN-ANALYSIS — the cross-signal correlation matrix C is
     eigen-decomposed. The dominant eigenvalue fraction λ₁/Σλ measures how much
     the whole system moves as ONE coherent mode (spectral coherence). This is
     the "tensor contraction reveals hidden correlations" step.

  4. PHASE ALIGNMENT — a Kuramoto order parameter over the dominant-frequency
     phases (amplitude-weighted) measures constructive vs destructive interference.

  5. HARMONY SCORE — H = w·[spectral_coherence, phase_alignment, balance].
     Dissonant pairs (strong NEGATIVE correlation — e.g. resource extraction up
     while human-wellness biometrics down) are detected and reported: the
     ledger's signal that a system is buying one dimension by destroying another.

Honest scope: H is a rigorous summary statistic of the supplied telemetry. The
module does NOT acquire biometric/quantum-sensory data or claim physiological
truth — it processes whatever time-series you feed it. Garbage in, garbage out.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

# Signals whose RISE indicates extraction/stress (so anticorrelation with
# wellness/sustainability signals is dissonance, not coincidence). Optional
# hint used only to label dissonant pairs more meaningfully.
_EXTRACTIVE_HINTS = ("extraction", "stress", "depletion", "carbon", "volatility", "load")
_VITALITY_HINTS = ("wellness", "biometric", "hrv", "health", "biodiversity", "prosperity", "regeneration")


@dataclass
class SignalSpectrum:
    name: str
    dominant_hz: float
    amplitude: float
    phase: float


@dataclass
class HarmonyResult:
    harmony_score: float            # H in [0,1]
    verdict: str                    # RESONANT | COHERENT | DISSONANT | FRACTURED
    spectral_coherence: float       # λ₁/Σλ normalized — one-mode dominance
    phase_alignment: float          # Kuramoto order parameter over dominant freqs
    amplitude_balance: float        # 1 - dispersion of signal energies
    spectra: list[SignalSpectrum]
    dissonant_pairs: list[dict[str, Any]]
    resonant_pairs: list[dict[str, Any]]
    n_signals: int
    n_samples: int
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "harmony_score": round(self.harmony_score, 4),
            "verdict": self.verdict,
            "spectral_coherence": round(self.spectral_coherence, 4),
            "phase_alignment": round(self.phase_alignment, 4),
            "amplitude_balance": round(self.amplitude_balance, 4),
            "spectra": [
                {"name": s.name, "dominant_hz": round(s.dominant_hz, 5),
                 "amplitude": round(s.amplitude, 4), "phase": round(s.phase, 4)}
                for s in self.spectra
            ],
            "dissonant_pairs": self.dissonant_pairs,
            "resonant_pairs": self.resonant_pairs,
            "n_signals": self.n_signals,
            "n_samples": self.n_samples,
            "notes": self.notes,
        }


def _verdict(h: float, coherence: float) -> str:
    if h >= 0.80 and coherence >= 0.70:
        return "RESONANT"
    if h >= 0.62:
        return "COHERENT"
    if h >= 0.42:
        return "DISSONANT"
    return "FRACTURED"


def _zscore(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    sd = x.std()
    if sd <= 1e-12:
        return x - x.mean()
    return (x - x.mean()) / sd


def _spectrum(name: str, x: np.ndarray, sample_rate_hz: float) -> SignalSpectrum:
    n = x.size
    if n < 2:
        return SignalSpectrum(name, 0.0, 0.0, 0.0)
    # Real FFT; ignore the DC bin for the dominant component.
    fft = np.fft.rfft(x)
    freqs = np.fft.rfftfreq(n, d=1.0 / max(sample_rate_hz, 1e-9))
    mag = np.abs(fft)
    if mag.size > 1:
        k = int(np.argmax(mag[1:]) + 1)
    else:
        k = 0
    return SignalSpectrum(name, float(freqs[k]), float(mag[k] / n), float(np.angle(fft[k])))


def _kuramoto(amplitudes: np.ndarray, phases: np.ndarray) -> float:
    a = np.clip(amplitudes, 0.0, None)
    total = float(np.sum(a))
    if total <= 1e-12:
        return 0.0
    z = np.sum(a * np.exp(1j * phases))
    return float(np.clip(np.abs(z) / total, 0.0, 1.0))


def _classify_pair(a: str, b: str) -> str:
    def kind(name: str) -> str:
        nl = name.lower()
        if any(h in nl for h in _EXTRACTIVE_HINTS):
            return "extractive"
        if any(h in nl for h in _VITALITY_HINTS):
            return "vitality"
        return "neutral"
    ka, kb = kind(a), kind(b)
    if {"extractive", "vitality"} == {ka, kb}:
        return "extraction-vs-vitality"
    return "general"


def harmony_from_signals(
    signals: dict[str, list[float] | np.ndarray],
    *,
    sample_rate_hz: float = 1.0,
    dissonance_threshold: float = -0.4,
    resonance_threshold: float = 0.6,
    weights: tuple[float, float, float] = (0.4, 0.4, 0.2),
) -> HarmonyResult:
    """
    Compute the Harmony Score H from a dict of named time-series signals.

    signals: {name: time-series}. Series of unequal length are truncated to the
        shortest. Examples of names: 'vibration_hz', 'economic_velocity',
        'biometric_hrv', 'ecological_extraction', 'weather_pressure'.
    sample_rate_hz: sampling rate for the FFT frequency axis (Hz).
    dissonance_threshold / resonance_threshold: correlation cutoffs for pairs.
    weights: (spectral_coherence, phase_alignment, amplitude_balance) blend.
    """
    names = list(signals.keys())
    if len(names) < 2:
        raise ValueError("Need at least 2 signals to compute harmonic coupling.")

    series = [np.asarray(signals[n], dtype=np.float64).ravel() for n in names]
    T = min(s.size for s in series)
    if T < 2:
        raise ValueError("Signals must have at least 2 samples.")
    S = np.vstack([_zscore(s[:T]) for s in series])  # (n_signals, T) signal tensor

    # Spectral features per signal.
    spectra = [_spectrum(names[i], S[i], sample_rate_hz) for i in range(len(names))]
    amps = np.array([sp.amplitude for sp in spectra])
    phases = np.array([sp.phase for sp in spectra])

    # Coupling matrix → eigen-analysis (spectral coherence = dominant-mode share).
    C = np.corrcoef(S)
    C = np.nan_to_num(C, nan=0.0)
    eigvals = np.sort(np.real(np.linalg.eigvalsh(C)))[::-1]
    eigvals = np.clip(eigvals, 0.0, None)
    total_eig = float(np.sum(eigvals)) or 1.0
    n = len(names)
    dom_share = float(eigvals[0] / total_eig)            # in [1/n, 1]
    spectral_coherence = float(np.clip((dom_share - 1.0 / n) / (1.0 - 1.0 / n), 0.0, 1.0))

    # Phase alignment (constructive interference) across dominant frequencies.
    phase_alignment = _kuramoto(amps, phases)

    # Amplitude balance — no single signal dominates the energy budget.
    a = np.clip(amps, 0.0, None)
    if a.sum() > 1e-12:
        p = a / a.sum()
        # normalized entropy of energy distribution → balance
        ent = -np.sum([pi * np.log(pi) for pi in p if pi > 0])
        amplitude_balance = float(np.clip(ent / np.log(n), 0.0, 1.0))
    else:
        amplitude_balance = 0.0

    w = np.array(weights, dtype=np.float64)
    w = w / w.sum()
    H = float(np.clip(
        w[0] * spectral_coherence + w[1] * phase_alignment + w[2] * amplitude_balance,
        0.0, 1.0,
    ))

    # Dissonant / resonant pairs from the coupling matrix.
    dissonant_pairs: list[dict[str, Any]] = []
    resonant_pairs: list[dict[str, Any]] = []
    for i in range(n):
        for j in range(i + 1, n):
            r = float(C[i, j])
            if r <= dissonance_threshold:
                dissonant_pairs.append({
                    "a": names[i], "b": names[j], "correlation": round(r, 3),
                    "kind": _classify_pair(names[i], names[j]),
                })
            elif r >= resonance_threshold:
                resonant_pairs.append({
                    "a": names[i], "b": names[j], "correlation": round(r, 3),
                })
    dissonant_pairs.sort(key=lambda d: d["correlation"])
    resonant_pairs.sort(key=lambda d: -d["correlation"])

    notes: list[str] = []
    clash = [d for d in dissonant_pairs if d["kind"] == "extraction-vs-vitality"]
    if clash:
        worst = clash[0]
        notes.append(
            f"Extraction-vs-vitality dissonance: '{worst['a']}' vs '{worst['b']}' "
            f"(r={worst['correlation']}). System gaining one dimension by destroying another."
        )
    if not dissonant_pairs:
        notes.append("No strong dissonant couplings detected.")

    return HarmonyResult(
        harmony_score=H,
        verdict=_verdict(H, spectral_coherence),
        spectral_coherence=spectral_coherence,
        phase_alignment=phase_alignment,
        amplitude_balance=amplitude_balance,
        spectra=spectra,
        dissonant_pairs=dissonant_pairs,
        resonant_pairs=resonant_pairs,
        n_signals=n,
        n_samples=T,
        notes=notes,
    )
