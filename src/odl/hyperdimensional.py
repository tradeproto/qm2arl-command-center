"""
Quantum Hyperdimensional Computing (QHDC) for the Omni-Dimensional Ledger.

Hyperdimensional Computing (HDC) / Vector Symbolic Architectures represent data
as very high-dimensional bipolar hypervectors (default 10,000-D, values in
{-1,+1}) with three algebraic operations:

  · bind(a, b)    = a ⊙ b            (elementwise product) — associate role↔value;
                                       self-inverse, similarity-dissimilar to inputs.
  · bundle(*hvs)  = sign(Σ hv)       (majority) — superpose into a set; stays
                                       similar to every component.
  · permute(hv,k) = roll(hv, k)      — encode order / position / time.
  · sim(a, b)     = (a·b)/D ∈ [-1,1] — cosine similarity (cheap, noise-robust).

We encode the ODL's omni-dimensional state (the 6 value dimensions + any harmonic
signals) into ONE holistic "state signature" hypervector via role-filler binding
+ bundling, then use an associative memory to recall the nearest stored
prototype (e.g. RESONANT vs DISSONANT).

THE QUANTUM CONNECTION (honest): an n-qubit state lives in a 2ⁿ-dimensional
Hilbert space — so a quantum state IS a unit hypervector, and state overlap
|⟨a|b⟩|² is a similarity measure. We reuse the QM2ARL quantum kernel
(src/quantum_geospatial, BlueQubit-ready) as the *quantum* similarity over the
low-dimensional value-vector signature. Classical HDC carries the big symbolic
binding; the quantum kernel provides the feature-space similarity/cleanup.
Honest scope: at ≤8 wires this is classically simulable — scale-ready
architecture, not a quantum-advantage claim today.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from .dimensions import DIMENSION_ORDER, Dimension

DEFAULT_DIM = 10_000
_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_HV_STORE = _REPO_ROOT / "data" / "odl_hypervectors.npz"


def _seed_from_name(name: str, base_seed: int) -> int:
    h = hashlib.sha256(f"{base_seed}:{name}".encode()).hexdigest()
    return int(h[:8], 16)


class HDCSpace:
    """A bipolar hyperdimensional space with item + level (continuous) memories."""

    def __init__(self, dim: int = DEFAULT_DIM, *, seed: int = 42, n_levels: int = 100):
        self.dim = int(dim)
        self.seed = int(seed)
        self.n_levels = int(n_levels)
        self._rng = np.random.default_rng(seed)
        self._items: dict[str, np.ndarray] = {}
        self._levels: np.ndarray | None = None

    # ── primitives ──────────────────────────────────────────────────────
    def random_hv(self, name: str | None = None) -> np.ndarray:
        if name is not None:
            rng = np.random.default_rng(_seed_from_name(name, self.seed))
        else:
            rng = self._rng
        return rng.choice(np.array([-1, 1], dtype=np.int8), size=self.dim)

    def bind(self, a: np.ndarray, b: np.ndarray) -> np.ndarray:
        return (a * b).astype(np.int8)

    def bundle(self, hvs: list[np.ndarray]) -> np.ndarray:
        if not hvs:
            return np.ones(self.dim, dtype=np.int8)
        s = np.sum(np.stack(hvs).astype(np.int32), axis=0)
        out = np.sign(s).astype(np.int8)
        # break ties (sum==0) deterministically toward +1
        out[out == 0] = 1
        return out

    def permute(self, hv: np.ndarray, k: int = 1) -> np.ndarray:
        return np.roll(hv, k).astype(np.int8)

    def similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        return float(np.dot(a.astype(np.float64), b.astype(np.float64)) / self.dim)

    # ── memories ────────────────────────────────────────────────────────
    def item(self, name: str) -> np.ndarray:
        """Deterministic symbol hypervector (stable across runs)."""
        if name not in self._items:
            self._items[name] = self.random_hv(name=name)
        return self._items[name]

    def _build_levels(self) -> np.ndarray:
        """Level hypervectors: level 0 random; each step flips dim/n_levels bits,
        so adjacent levels are similar and extremes are near-orthogonal."""
        rng = np.random.default_rng(_seed_from_name("__levels__", self.seed))
        base = rng.choice(np.array([-1, 1], dtype=np.int8), size=self.dim)
        levels = [base.copy()]
        flips_per_step = max(1, self.dim // (2 * self.n_levels))
        cur = base.copy()
        order = rng.permutation(self.dim)
        idx = 0
        for _ in range(self.n_levels):
            cur = cur.copy()
            sel = order[idx: idx + flips_per_step]
            cur[sel] *= -1
            idx += flips_per_step
            levels.append(cur)
        return np.stack(levels)

    def level(self, value: float) -> np.ndarray:
        """Encode a continuous value in [0,1] to a level hypervector."""
        if self._levels is None:
            self._levels = self._build_levels()
        v = float(np.clip(value, 0.0, 1.0))
        li = int(round(v * self.n_levels))
        return self._levels[li]

    # ── encoding ────────────────────────────────────────────────────────
    def encode_record(self, fields: dict[str, float]) -> np.ndarray:
        """Role-filler encode {name: value in [0,1]} → one holistic hypervector."""
        bound = [self.bind(self.item(name), self.level(val)) for name, val in fields.items()]
        return self.bundle(bound)


@dataclass
class RecallResult:
    label: str
    score: float
    ranked: list[tuple[str, float]] = field(default_factory=list)


class AssociativeMemory:
    """Cleanup / classification memory over stored prototype hypervectors."""

    def __init__(self, space: HDCSpace):
        self.space = space
        self._proto: dict[str, np.ndarray] = {}
        self._examples: dict[str, list[np.ndarray]] = {}

    def learn(self, label: str, hv: np.ndarray) -> None:
        """Add an example; the prototype is the bundle of all examples of label."""
        self._examples.setdefault(label, []).append(hv)
        self._proto[label] = self.space.bundle(self._examples[label])

    def recall(self, hv: np.ndarray) -> RecallResult:
        if not self._proto:
            return RecallResult("<empty>", 0.0, [])
        ranked = sorted(
            ((lbl, self.space.similarity(hv, p)) for lbl, p in self._proto.items()),
            key=lambda kv: -kv[1],
        )
        return RecallResult(ranked[0][0], ranked[0][1], ranked)


# ──────────────────────────────────────────────────────────────────────────
# ODL integration: encode a resonance state + signals into a state signature
# ──────────────────────────────────────────────────────────────────────────
def state_signature(
    space: HDCSpace,
    dimensions: dict[str, float] | None = None,
    signals: dict[str, float] | None = None,
) -> np.ndarray:
    """
    Encode an ODL omni-dimensional state into one hypervector.

    dimensions: {dimension_name: value in [0,1]} (canonical 6 value axes).
    signals: optional {signal_name: value in [0,1]} (e.g. normalized harmonic).
    """
    fields: dict[str, float] = {}
    if dimensions:
        for d in DIMENSION_ORDER:
            key = d.value
            if key in dimensions:
                fields[f"dim:{key}"] = float(dimensions[key])
    if signals:
        for k, v in signals.items():
            fields[f"sig:{k}"] = float(np.clip(v, 0.0, 1.0))
    if not fields:
        raise ValueError("Provide at least one dimension or signal to encode.")
    return space.encode_record(fields)


# ──────────────────────────────────────────────────────────────────────────
# Quantum-HDC bridge: quantum-kernel similarity over the value-vector signature
# ──────────────────────────────────────────────────────────────────────────
def quantum_similarity(
    a_values: np.ndarray, b_values: np.ndarray, *, vqc_backend: str = ""
) -> tuple[float, str]:
    """
    Quantum-kernel similarity |⟨φ(a)|φ(b)⟩|² between two low-dim value vectors,
    using the QM2ARL VQC quantum kernel on the BlueQubit-ready backend ladder.
    Returns (similarity in [0,1], active_backend).
    """
    import os

    try:
        from src.quantum_geospatial import get_quantum_anomaly_detector

        n = int(np.asarray(a_values).size)
        det = get_quantum_anomaly_detector(
            feature_dim=max(2, min(n, 8)),
            gamma=0.5,
            use_vqc=True,
            vqc_seed=42,
            vqc_max_wires=max(2, min(n, 8)),
            vqc_backend=vqc_backend or os.environ.get("ODL_QUANTUM_BACKEND", ""),
            bluequbit_token=os.environ.get("BLUEQUBIT_API_TOKEN", ""),
        )
        return float(det.quantum_kernel(a_values, b_values)), det.active_backend
    except Exception:
        a = np.asarray(a_values, dtype=np.float64)
        b = np.asarray(b_values, dtype=np.float64)
        a = a / (np.linalg.norm(a) + 1e-12)
        b = b / (np.linalg.norm(b) + 1e-12)
        dot = float(np.clip(np.dot(a, b), -1.0, 1.0))
        return dot * dot, "classical-fallback"


# ──────────────────────────────────────────────────────────────────────────
# Bit-packing + persistent hypervector memory bank (for the ledger)
# ──────────────────────────────────────────────────────────────────────────
def pack_bipolar(hv: np.ndarray) -> np.ndarray:
    """Pack a {-1,+1} hypervector into bits (8x smaller). +1→1, -1→0."""
    return np.packbits((np.asarray(hv) > 0).astype(np.uint8))


def unpack_bipolar(packed: np.ndarray, dim: int) -> np.ndarray:
    """Inverse of pack_bipolar → {-1,+1} int8 of length `dim`."""
    bits = np.unpackbits(np.asarray(packed, dtype=np.uint8))[:dim]
    return (bits.astype(np.int8) * 2 - 1).astype(np.int8)


def fingerprint(hv: np.ndarray, n_bits: int = 64) -> str:
    """Short stable hex fingerprint (first n_bits) for the ledger epoch body."""
    bits = (np.asarray(hv[:n_bits]) > 0).astype(np.uint8)
    packed = np.packbits(bits).tobytes()
    return packed.hex()


@dataclass
class HVMatch:
    epoch_id: str
    similarity: float


class HyperLedgerMemory:
    """
    Persistent bit-packed hypervector bank keyed by epoch_id — an ENGRAM-style
    associative memory for the ledger. Enables instant cosine similarity search
    across all historical resonance epochs via a single matmul.

    Stored as data/odl_hypervectors.npz: ids (object), packed (N × ceil(dim/8)
    uint8), and dim/seed meta so signatures stay comparable across runs.
    """

    def __init__(self, path: str | Path | None = None, *, dim: int = DEFAULT_DIM, seed: int = 42):
        self.path = Path(path) if path else _DEFAULT_HV_STORE
        self.dim = int(dim)
        self.seed = int(seed)
        self._ids: list[str] = []
        self._packed: list[np.ndarray] = []
        self._load()

    def _load(self) -> None:
        if not self.path.is_file():
            return
        try:
            data = np.load(self.path, allow_pickle=True)
            file_dim = int(data["dim"]) if "dim" in data else self.dim
            if file_dim != self.dim:
                # Incompatible signature space; start fresh in-memory (don't clobber file).
                return
            self._ids = list(data["ids"].tolist())
            packed = data["packed"]
            self._packed = [packed[i] for i in range(packed.shape[0])] if packed.size else []
        except Exception:
            self._ids, self._packed = [], []

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        packed = np.vstack(self._packed) if self._packed else np.zeros((0, 0), dtype=np.uint8)
        np.savez(self.path, ids=np.array(self._ids, dtype=object),
                 packed=packed, dim=self.dim, seed=self.seed)

    def add(self, epoch_id: str, hv: np.ndarray) -> None:
        self._ids.append(str(epoch_id))
        self._packed.append(pack_bipolar(hv))
        self._save()

    def height(self) -> int:
        return len(self._ids)

    def _matrix(self) -> np.ndarray:
        if not self._packed:
            return np.zeros((0, self.dim), dtype=np.int8)
        return np.vstack([unpack_bipolar(p, self.dim) for p in self._packed])

    def search(self, query_hv: np.ndarray, *, top_k: int = 5,
               exclude: set[str] | None = None) -> list[HVMatch]:
        """Return the top_k most similar historical epochs (cosine over ±1)."""
        if not self._ids:
            return []
        M = self._matrix().astype(np.float64)
        q = np.asarray(query_hv, dtype=np.float64)
        sims = (M @ q) / float(self.dim)
        order = np.argsort(-sims)
        out: list[HVMatch] = []
        exclude = exclude or set()
        for i in order:
            eid = self._ids[int(i)]
            if eid in exclude:
                continue
            out.append(HVMatch(eid, float(sims[int(i)])))
            if len(out) >= top_k:
                break
        return out


def main() -> int:
    """Demo: classify a new omni-dimensional state vs RESONANT/DISSONANT prototypes."""
    space = HDCSpace(dim=10_000, seed=7)
    mem = AssociativeMemory(space)

    # Resonant prototype: all dimensions high & balanced.
    for _ in range(5):
        d = {dim.value: float(np.clip(0.85 + 0.05 * np.random.randn(), 0, 1)) for dim in DIMENSION_ORDER}
        mem.learn("RESONANT", state_signature(space, d))
    # Dissonant prototype: prosperity high, planet/health collapsed (extractive).
    for _ in range(5):
        d = {dim.value: float(np.clip(0.6 + 0.1 * np.random.randn(), 0, 1)) for dim in DIMENSION_ORDER}
        d["planet"] = float(np.clip(0.2 + 0.05 * np.random.randn(), 0, 1))
        d["health"] = float(np.clip(0.25 + 0.05 * np.random.randn(), 0, 1))
        d["prosperity"] = float(np.clip(0.92 + 0.03 * np.random.randn(), 0, 1))
        mem.learn("DISSONANT", state_signature(space, d))

    print("\n=== Quantum Hyperdimensional Computing — ODL state classifier ===")
    print(f"Hypervector dim: {space.dim} (bipolar)\n")

    test_resonant = {dim.value: 0.84 for dim in DIMENSION_ORDER}
    test_extractive = {dim.value: 0.6 for dim in DIMENSION_ORDER}
    test_extractive.update(planet=0.18, health=0.22, prosperity=0.95)

    for label, d in [("balanced/high", test_resonant), ("extractive", test_extractive)]:
        hv = state_signature(space, d)
        r = mem.recall(hv)
        vec = np.array([d[dim.value] for dim in DIMENSION_ORDER])
        proto_res = np.array([0.85] * len(DIMENSION_ORDER))
        q, backend = quantum_similarity(vec, proto_res)
        print(f"state '{label}':")
        print(f"  HDC recall   → {r.label}  (sim {r.score:.3f})   ranked={[ (l, round(s,3)) for l,s in r.ranked]}")
        print(f"  Quantum sim to RESONANT proto → {q:.3f}  (backend: {backend})")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
