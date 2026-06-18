"""
Live data feeds → harmonic signals for the Omni-Dimensional Ledger.

Bridges the operational TELPAI government/geophysical feeds (USGS seismic, EIA
prices, NASA POWER, ESA Swarm, NASA FIRMS, ...) into the harmonic Harmony Score
(src/odl/harmonic.py).

Engineering reality: the harmonic layer needs TIME-SERIES, but most feeds return
a point snapshot per call. So this module:

  1. EXTRACTS a scalar per signal from each feed (defensive: candidate-key list
     + numeric fallback; one cached call per underlying fetcher).
  2. BUFFERS snapshots over time in a persisted rolling SignalBuffer
     (data/odl_signals.jsonl) — each poll appends a timestamped sample.
  3. Once enough samples accumulate, builds per-signal series and computes the
     Harmony Score.

Operate it by scheduling `poll_once` (e.g. cron / a loop) so the buffer fills;
`harmony_from_live` then reports either the Harmony Score or "accumulating".

Offline/sandbox: live HTTP may be blocked; every fetch is wrapped, failures are
reported per-signal, and `synthesize_history` provides a clearly-labeled
SYNTHETIC buffer for pipeline testing without network.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import numpy as np

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_BUFFER = _REPO_ROOT / "data" / "odl_signals.jsonl"


# Each signal: which api_server fetcher to call, kwargs builder, and the ordered
# candidate keys to read a numeric value from. Defensive by design.
@dataclass(frozen=True)
class FeedSignal:
    name: str
    fetcher: str
    kwargs: tuple[tuple[str, Any], ...]   # static kwargs; lat/lon/radius injected
    keys: tuple[str, ...]
    category: str


FEED_SIGNALS: tuple[FeedSignal, ...] = (
    FeedSignal("economic_price_wti", "_eia_fetch", (("series", "wti"),),
               ("current_price_usd", "price", "value", "7_day_avg"), "economic"),
    FeedSignal("seismic_magnitude", "fetch_usgs_seismic", (),
               ("strongest_magnitude", "max_magnitude"), "geo"),
    FeedSignal("seismic_events_24h", "fetch_usgs_seismic", (),
               ("total_events_24h", "total_detections_24h"), "geo"),
    FeedSignal("thermal_flares", "_firms_fetch",
               (("__inject__", "latlon"), ("__inject__", "radius")),
               ("high_confidence_flares", "total_detections_24h", "detections"), "thermal"),
    FeedSignal("weather_irradiance", "_power_fetch", (("__inject__", "latlon"),),
               ("avg_global_horizontal_irradiance", "ghi", "irradiance", "value"), "weather"),
    FeedSignal("geomagnetic_intensity", "_swarm_fetch",
               (("__inject__", "latlon"), ("__inject__", "radius")),
               ("mean_intensity_nt", "magnetic_intensity", "mean", "value"), "geomagnetic"),
)


def _first_numeric(payload: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    if not isinstance(payload, dict):
        return None
    for k in keys:
        v = payload.get(k)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return float(v)
    # generic fallback: first finite numeric leaf
    for v in payload.values():
        if isinstance(v, (int, float)) and not isinstance(v, bool) and np.isfinite(v):
            return float(v)
    return None


def collect_live_signals(
    lat: float, lon: float, *, radius_km: float = 250.0
) -> dict[str, Any]:
    """
    Pull one live snapshot scalar per signal. Returns
    {"values": {name: float}, "errors": {name: msg}, "timestamp_utc": ...}.
    Each underlying fetcher is called at most once (cached).
    """
    try:
        import api_server as srv
    except Exception as e:
        return {"values": {}, "errors": {"_import": f"{type(e).__name__}: {e}"},
                "timestamp_utc": datetime.now(timezone.utc).isoformat()}

    cache: dict[tuple, dict[str, Any]] = {}
    values: dict[str, float] = {}
    errors: dict[str, str] = {}

    for sig in FEED_SIGNALS:
        fn: Callable | None = getattr(srv, sig.fetcher, None)
        if fn is None:
            errors[sig.name] = f"fetcher {sig.fetcher} not found"
            continue
        kwargs: dict[str, Any] = {}
        for k, v in sig.kwargs:
            if k == "__inject__" and v == "latlon":
                kwargs.update(lat=lat, lon=lon)
            elif k == "__inject__" and v == "radius":
                kwargs.update(radius_km=radius_km)
            else:
                kwargs[k] = v
        cache_key = (sig.fetcher, tuple(sorted(kwargs.items())))
        try:
            if cache_key not in cache:
                cache[cache_key] = fn(**kwargs)
            payload = cache[cache_key]
            val = _first_numeric(payload, sig.keys)
            if val is None:
                errors[sig.name] = "no numeric field"
            else:
                values[sig.name] = val
        except Exception as e:
            errors[sig.name] = f"{type(e).__name__}: {e}"

    return {
        "values": values,
        "errors": errors,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "location": {"lat": lat, "lon": lon, "radius_km": radius_km},
    }


class SignalBuffer:
    """Persisted append-only rolling buffer of timestamped signal snapshots."""

    def __init__(self, path: str | Path | None = None, *, max_rows: int = 4096):
        self.path = Path(path) if path else _DEFAULT_BUFFER
        self.max_rows = max_rows

    def append(self, values: dict[str, float], *, timestamp: str | None = None,
               source: str = "live") -> dict[str, Any]:
        row = {
            "t": timestamp or datetime.now(timezone.utc).isoformat(),
            "source": source,
            "values": {k: float(v) for k, v in values.items()},
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
        self._truncate()
        return row

    def _truncate(self) -> None:
        if not self.path.is_file():
            return
        lines = self.path.read_text(encoding="utf-8").splitlines()
        if len(lines) > self.max_rows:
            self.path.write_text("\n".join(lines[-self.max_rows:]) + "\n", encoding="utf-8")

    def rows(self) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        out = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                out.append(json.loads(line))
        return out

    def series(self, *, min_samples: int = 8) -> dict[str, list[float]]:
        """Per-signal series for signals present in at least min_samples rows."""
        rows = self.rows()
        names: dict[str, list[float]] = {}
        for r in rows:
            for k, v in r.get("values", {}).items():
                names.setdefault(k, [])
        for name in list(names.keys()):
            seq = [r["values"][name] for r in rows if name in r.get("values", {})]
            if len(seq) >= min_samples:
                names[name] = seq
            else:
                del names[name]
        return names

    def height(self) -> int:
        return len(self.rows())


def poll_once(lat: float, lon: float, *, buffer: SignalBuffer | None = None,
              radius_km: float = 250.0) -> dict[str, Any]:
    """Collect one live snapshot and append it to the buffer."""
    buffer = buffer or SignalBuffer()
    snap = collect_live_signals(lat, lon, radius_km=radius_km)
    if snap["values"]:
        buffer.append(snap["values"], timestamp=snap["timestamp_utc"], source="live")
    return {**snap, "buffer_height": buffer.height()}


def live_harmonic_signals(buffer: SignalBuffer | None = None, *,
                          min_samples: int = 8) -> dict[str, list[float]]:
    buffer = buffer or SignalBuffer()
    return buffer.series(min_samples=min_samples)


def harmony_from_live(
    lat: float | None = None,
    lon: float | None = None,
    *,
    buffer: SignalBuffer | None = None,
    poll: bool = True,
    min_samples: int = 8,
    sample_rate_hz: float = 1.0,
    radius_km: float = 250.0,
) -> dict[str, Any]:
    """
    Poll the live feeds (optional), update the buffer, and compute the Harmony
    Score if enough samples have accumulated; otherwise report 'accumulating'.
    """
    buffer = buffer or SignalBuffer()
    poll_result = None
    if poll and lat is not None and lon is not None:
        poll_result = poll_once(lat, lon, buffer=buffer, radius_km=radius_km)

    sigs = live_harmonic_signals(buffer, min_samples=min_samples)
    if len(sigs) < 2:
        return {
            "status": "accumulating",
            "buffer_height": buffer.height(),
            "signals_ready": list(sigs.keys()),
            "min_samples": min_samples,
            "poll": poll_result,
            "note": "Need >= 2 signals with >= min_samples each. Keep polling "
                    "(schedule poll_once) to fill the buffer.",
        }

    from .harmonic import harmony_from_signals

    result = harmony_from_signals(sigs, sample_rate_hz=sample_rate_hz).as_dict()
    return {"status": "ok", "buffer_height": buffer.height(),
            "harmony": result, "poll": poll_result}


def synthesize_history(
    buffer: SignalBuffer,
    *,
    n: int = 64,
    names: tuple[str, ...] = ("economic_price_wti", "weather_irradiance",
                              "seismic_events_24h", "thermal_flares"),
    seed: int = 0,
) -> int:
    """
    Append N clearly-labeled SYNTHETIC samples for pipeline testing without
    network. Returns the number of rows appended. NOT live data.
    """
    rng = np.random.default_rng(seed)
    t = np.linspace(0, 6 * np.pi, n)
    base = {nm: (np.sin(t + i) + 0.1 * rng.standard_normal(n))
            for i, nm in enumerate(names)}
    for k in range(n):
        buffer.append({nm: float(base[nm][k]) for nm in names},
                      timestamp=datetime.now(timezone.utc).isoformat(),
                      source="synthetic")
    return n


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="ODL live data feeds → harmonic buffer")
    ap.add_argument("--lat", type=float, default=30.6)
    ap.add_argument("--lon", type=float, default=-95.1)
    ap.add_argument("--radius-km", type=float, default=250.0)
    ap.add_argument("--buffer", default=str(_DEFAULT_BUFFER))
    ap.add_argument("--poll", action="store_true", help="collect one live snapshot")
    ap.add_argument("--harmony", action="store_true", help="compute harmony from buffer")
    ap.add_argument("--synthetic", type=int, default=0, help="append N synthetic samples (test)")
    ap.add_argument("--min-samples", type=int, default=8)
    args = ap.parse_args()

    buf = SignalBuffer(args.buffer)

    if args.synthetic:
        added = synthesize_history(buf, n=args.synthetic)
        print(f"Appended {added} SYNTHETIC samples → buffer height {buf.height()}")

    if args.poll:
        r = poll_once(args.lat, args.lon, buffer=buf, radius_km=args.radius_km)
        print(f"Polled live feeds @ ({args.lat},{args.lon}) → "
              f"{len(r['values'])} signals, {len(r['errors'])} errors; "
              f"buffer height {r['buffer_height']}")
        if r["values"]:
            print("  values:", {k: round(v, 3) for k, v in r["values"].items()})
        if r["errors"]:
            print("  errors:", r["errors"])

    if args.harmony:
        out = harmony_from_live(buffer=buf, poll=False, min_samples=args.min_samples)
        if out["status"] != "ok":
            print(f"[{out['status']}] {out['note']}  (ready: {out['signals_ready']})")
        else:
            h = out["harmony"]
            print(f"Harmony H={h['harmony_score']}  [{h['verdict']}]  "
                  f"coherence={h['spectral_coherence']} phase={h['phase_alignment']}")
            for d in h["dissonant_pairs"][:3]:
                print("  dissonant:", d)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
