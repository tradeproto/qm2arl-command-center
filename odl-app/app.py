"""
Omni-Dimensional Ledger — Live Resonance + Ledger Explorer

Run:  streamlit run odl-app/app.py --server.port 8504
API:  uvicorn api_server:app --port 8000  (or pm2 telpai-api)
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any

import plotly.graph_objects as go
import requests
import streamlit as st

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
_ODL_APP = os.path.join(_REPO_ROOT, "odl-app")
if _ODL_APP not in sys.path:
    sys.path.insert(0, _ODL_APP)

from brain_ui import plot_brain_graph, plot_coupling_heatmap, render_coverage_banner

API_BASE = os.getenv("ODL_API_URL", os.getenv("TELPAI_API_URL", "http://127.0.0.1:8000"))

st.set_page_config(
    page_title="ODL — System Resonance",
    page_icon="◎",
    layout="wide",
    initial_sidebar_state="expanded",
)

DIM_COLORS = {
    "prosperity": "#2ecc71",
    "planet": "#27ae60",
    "equity": "#3498db",
    "health": "#e74c3c",
    "knowledge": "#9b59b6",
    "connection": "#f39c12",
}


def api_get(path: str, timeout: float = 12.0) -> dict[str, Any] | None:
    try:
        r = requests.get(f"{API_BASE}{path}", timeout=timeout)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def api_post(path: str, body: dict | None = None, timeout: float = 120.0) -> dict[str, Any] | None:
    try:
        r = requests.post(f"{API_BASE}{path}", json=body or {}, timeout=timeout)
        if r.status_code in (200, 201):
            return r.json()
    except Exception:
        pass
    return None


def api_put(path: str, body: dict | None = None, timeout: float = 30.0) -> dict[str, Any] | None:
    try:
        r = requests.put(f"{API_BASE}{path}", json=body or {}, timeout=timeout)
        if r.status_code in (200, 201):
            return r.json()
    except Exception:
        pass
    return None


def local_step(**kwargs) -> dict[str, Any]:
    from src.odl.engine import SystemResonanceEngine
    from src.odl.anchor import anchor_epoch

    eng = SystemResonanceEngine(
        governor_tier=kwargs.get("tier", "GAI"),
        vqc_backend=kwargs.get("backend", ""),
    )
    out = eng.step(seal=kwargs.get("seal", False))
    if kwargs.get("anchor"):
        out["anchor"] = anchor_epoch(out["epoch"], dry_run=kwargs.get("anchor_dry_run", False))
    return out


def verdict_color(verdict: str) -> str:
    return {
        "RESONANT": "#2ecc71",
        "COHERENT": "#3498db",
        "DISSONANT": "#f39c12",
        "FRACTURED": "#e74c3c",
    }.get(verdict, "#95a5a6")


def get_harmony(api_ok: bool) -> dict[str, Any] | None:
    """Current harmonic Harmony Score from the accumulated signal buffer."""
    if api_ok:
        h = api_get("/odl/harmony")
        if h is not None:
            return h
    try:
        from src.odl.feeds import SignalBuffer, harmony_from_live
        return harmony_from_live(buffer=SignalBuffer(), poll=False, min_samples=8)
    except Exception as e:
        return {"status": "error", "note": str(e)}


def get_nearest_history(api_ok: bool, top_k: int = 5) -> dict[str, Any] | None:
    """Nearest historical epochs to the head, by HDC state signature."""
    if api_ok:
        s = api_get(f"/odl/similar?top_k={top_k}")
        if s is not None:
            return s
    try:
        from src.odl.ledger import OmniDimensionalLedger
        from src.odl.engine import SystemResonanceEngine
        head = OmniDimensionalLedger().head()
        if not head:
            return {"status": "empty", "matches": []}
        dims = (head.get("resonance") or {}).get("dimensions") or {}
        eng = SystemResonanceEngine()
        matches = eng.search_history(dims, top_k=top_k + 1)
        head_id = head.get("epoch_id")
        matches = [m for m in matches if m.get("epoch_id") != head_id][:top_k]
        return {"status": "ok", "head_epoch": head_id, "matches": matches}
    except Exception as e:
        return {"status": "error", "note": str(e)}


def do_poll_feeds(api_ok: bool, lat: float, lon: float, synthetic: int = 0) -> dict[str, Any] | None:
    if api_ok:
        r = api_post("/odl/feeds/poll", {"lat": lat, "lon": lon, "synthetic": synthetic})
        if r is not None:
            return r
    try:
        from src.odl.feeds import SignalBuffer, poll_once, synthesize_history
        buf = SignalBuffer()
        if synthetic > 0:
            synthesize_history(buf, n=synthetic)
        return poll_once(lat, lon, buffer=buf)
    except Exception as e:
        return {"values": {}, "errors": {"_local": str(e)}, "buffer_height": 0}


# ─── Sidebar ───
with st.sidebar:
    st.title("◎ ODL")
    st.caption("Omni-Dimensional Ledger · System Resonance")
    st.markdown(f"**API:** `{API_BASE}`")

    health = api_get("/odl/health")
    api_ok = health is not None
    if api_ok:
        st.success(f"API online · height {health.get('ledger_height', 0)}")
        if health.get("anchor_ready"):
            st.info(f"Anchor ready · {health.get('anchor_chain', 'sepolia')}")
        else:
            missing = health.get("anchor_missing_env") or []
            st.warning(f"Anchor: set {', '.join(missing) if missing else 'env vars'}")
    else:
        st.warning("API offline — using in-process fallback")

    st.divider()
    page = st.radio(
        "Navigate",
        ["Live Resonance", "ODL Brain", "Ledger Explorer", "Framework Status"],
        label_visibility="collapsed",
    )

    st.divider()
    st.subheader("Actions")
    run_step = st.button("▶ Run Resonance Cycle", use_container_width=True, type="primary")
    with_seal = st.checkbox("Dragon Seal after step", value=False)
    with_anchor = st.checkbox("Anchor on-chain after step", value=False)
    anchor_dry = st.checkbox("Anchor dry-run only", value=True)
    seal_only = st.button("Seal head epoch", use_container_width=True)
    anchor_only = st.button("Anchor head epoch", use_container_width=True)

    st.divider()
    st.subheader("Live feeds → Harmony")
    feed_lat = st.number_input("Latitude", value=30.6, format="%.4f")
    feed_lon = st.number_input("Longitude", value=-95.1, format="%.4f")
    poll_feeds = st.button("◷ Poll live feeds", use_container_width=True)
    seed_demo = st.button("Seed synthetic demo (48)", use_container_width=True)

# ─── Action handlers ───
action_result: dict[str, Any] | None = None
if run_step or seal_only or anchor_only:
    with st.spinner("Running ODL cycle…"):
        if run_step:
            if api_ok:
                action_result = api_post(
                    "/odl/step",
                    {
                        "seal": with_seal,
                        "anchor": with_anchor,
                        "anchor_dry_run": anchor_dry,
                        "tier": "GAI",
                    },
                )
            else:
                action_result = local_step(seal=with_seal, anchor=with_anchor, anchor_dry_run=anchor_dry)
        elif seal_only:
            action_result = api_post("/odl/seal") if api_ok else None
            if not action_result:
                from src.odl.ledger import OmniDimensionalLedger
                action_result = {"dragon_seal": OmniDimensionalLedger().seal_head()}
        elif anchor_only:
            action_result = api_post("/odl/anchor", {"dry_run": anchor_dry}) if api_ok else None
            if not action_result:
                from src.odl.anchor import anchor_epoch
                from src.odl.ledger import OmniDimensionalLedger
                head = OmniDimensionalLedger().head()
                action_result = {"anchor": anchor_epoch(head, dry_run=anchor_dry)} if head else {"error": "empty ledger"}

if poll_feeds or seed_demo:
    with st.spinner("Polling live data feeds…"):
        pr = do_poll_feeds(api_ok, feed_lat, feed_lon, synthetic=48 if seed_demo else 0)
    if pr:
        nvals = len(pr.get("values", {}))
        st.toast(f"Feeds polled: {nvals} signals · buffer {pr.get('buffer_height', 0)}", icon="◷")

# ─── Load state ───
res_data = api_get("/odl/resonance") if api_ok else None
ledger_data = api_get("/odl/ledger?limit=100") if api_ok else None
framework_data = api_get("/odl/framework") if api_ok else None
brain_data = api_get("/odl/brain") if api_ok else None
dims_data = api_get("/odl/dimensions") if api_ok else None

if not res_data and not api_ok:
    from src.odl.ledger import OmniDimensionalLedger
    from src.odl.brain import brain_state
    from src.odl.dimension_config import coupling_matrix, list_dimensions
    head = OmniDimensionalLedger().head()
    if head:
        res_data = {"status": "ok", "epoch": head, "resonance": head.get("resonance"), "governance": head.get("governance")}
    if ledger_data is None:
        ledger = OmniDimensionalLedger()
        ledger_data = {"height": ledger.height(), "epochs": list(reversed(ledger.entries())), "chain": ledger.verify_chain()}
    if brain_data is None:
        brain_data = brain_state(head.get("resonance") if head else None)
    if dims_data is None:
        ids, matrix = coupling_matrix()
        dims_data = {"dimensions": list_dimensions(), "coupling": {"ids": ids, "matrix": matrix}}

if action_result:
    st.toast("ODL action complete", icon="✅")

# ═══════════════════════════════════════════════════════════════
if page == "Live Resonance":
    st.header("Live System Resonance")

    cov_banner = (brain_data or {}).get("coverage") or api_get("/odl/brain/coverage")
    if not cov_banner and res_data and res_data.get("resonance"):
        try:
            from src.odl.brain import coverage_honesty
            cov_banner = coverage_honesty(res_data["resonance"])
        except Exception:
            pass
    render_coverage_banner(cov_banner)

    if not res_data or res_data.get("status") == "empty":
        st.info("No resonance epochs yet. Click **Run Resonance Cycle** in the sidebar.")
    else:
        r = res_data.get("resonance") or {}
        g = res_data.get("governance") or {}
        epoch = res_data.get("epoch") or {}

        c1, c2, c3, c4 = st.columns(4)
        verdict = r.get("verdict", "—")
        c1.metric("System Resonance R", f"{r.get('system_resonance', 0):.3f}")
        c2.metric("Verdict", verdict)
        c3.metric("Governor", g.get("decision", "—"))
        c4.metric("Coverage", f"{r.get('coverage', {}).get('coverage_pct', 0):.0f}%")

        st.markdown(
            f"<div style='height:6px;background:{verdict_color(verdict)};border-radius:3px;margin-bottom:1rem'></div>",
            unsafe_allow_html=True,
        )

        left, right = st.columns([1, 1])
        dims = r.get("dimensions") or {}
        with left:
            st.subheader("Value dimensions")
            if dims:
                fig = go.Figure()
                labels = list(dims.keys())
                values = [dims[k] for k in labels]
                fig.add_trace(go.Scatterpolar(
                    r=values + [values[0]],
                    theta=[k.title() for k in labels] + [labels[0].title()],
                    fill="toself",
                    line_color="#9b59b6",
                    fillcolor="rgba(155,89,182,0.25)",
                ))
                fig.update_layout(
                    polar=dict(radialaxis=dict(range=[0, 1], showticklabels=False)),
                    height=360,
                    margin=dict(l=40, r=40, t=30, b=30),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                )
                st.plotly_chart(fig, use_container_width=True)

            for k, v in dims.items():
                st.progress(float(v), text=f"{k.title()} — {v:.3f}")

        with right:
            st.subheader("Coherence breakdown")
            m1, m2, m3 = st.columns(3)
            m1.metric("Magnitude M", f"{r.get('magnitude', 0):.3f}")
            m2.metric("Phase ρ", f"{r.get('phase_coherence', 0):.3f}")
            m3.metric("Quantum Q", f"{r.get('quantum_coherence', 0):.3f}")
            st.caption(f"Backend: `{r.get('backend', '—')}` · Binding: **{r.get('binding_dimension', '—')}** @ {r.get('binding_value', 0):.2f}")

            st.subheader("Governor directive")
            st.info(g.get("directive", "—"))
            if g.get("breached_floors"):
                st.error(f"Breached floors: {g.get('breached_floors')}")

            cov = r.get("coverage") or {}
            if cov.get("missing"):
                st.warning(f"Uncovered (defaulted to target): {', '.join(cov['missing'])}")

            st.subheader("Head epoch")
            st.code(epoch.get("epoch_id", "—"), language=None)
            st.link_button("Dragon Seal verify", epoch.get("verify_url", "https://dragonseal.io"), use_container_width=True)
            anchor = epoch.get("anchor")
            if anchor:
                st.json(anchor)
            elif action_result and action_result.get("anchor"):
                st.json(action_result["anchor"])

        # ─── Harmonic Resonance + Nearest History ───
        st.divider()
        h_col, n_col = st.columns([1, 1])

        with h_col:
            st.subheader("Harmonic Resonance")
            st.caption("Harmony Score from live signal feeds (FFT + coupling eigen-analysis).")
            harmony = get_harmony(api_ok)
            if not harmony or harmony.get("status") == "error":
                st.warning(f"Harmony unavailable: {(harmony or {}).get('note', 'no data')}")
            elif harmony.get("status") == "accumulating":
                ready = harmony.get("signals_ready", [])
                st.info(
                    f"Accumulating — buffer height {harmony.get('buffer_height', 0)}, "
                    f"{len(ready)} signal(s) ready. Use **Poll live feeds** (or **Seed "
                    f"synthetic demo**) in the sidebar to fill the buffer."
                )
            else:
                hh = harmony.get("harmony") or {}
                hv = hh.get("verdict", "—")
                hc1, hc2, hc3 = st.columns(3)
                hc1.metric("Harmony H", f"{hh.get('harmony_score', 0):.3f}")
                hc2.metric("Verdict", hv)
                hc3.metric("Phase align", f"{hh.get('phase_alignment', 0):.3f}")
                st.markdown(
                    f"<div style='height:5px;background:{verdict_color(hv)};border-radius:3px'></div>",
                    unsafe_allow_html=True,
                )
                st.caption(
                    f"Spectral coherence {hh.get('spectral_coherence', 0):.3f} · "
                    f"amplitude balance {hh.get('amplitude_balance', 0):.3f} · "
                    f"{hh.get('n_signals', 0)} signals × {hh.get('n_samples', 0)} samples"
                )
                diss = hh.get("dissonant_pairs") or []
                if diss:
                    st.markdown("**Dissonant couplings** (one dimension rising as another falls):")
                    for d in diss[:4]:
                        kind = " · extraction-vs-vitality" if d.get("kind") == "extraction-vs-vitality" else ""
                        st.write(f"- `{d['a']}` ✕ `{d['b']}`  (r = {d['correlation']}){kind}")
                else:
                    st.success("No strong dissonant couplings detected.")

        with n_col:
            st.subheader("Nearest in History")
            st.caption("Past epochs most like this state (HDC hypervector similarity).")
            near = get_nearest_history(api_ok, top_k=5)
            hdc_src = (epoch.get("sources") or {}).get("hdc") or {}
            if hdc_src.get("fingerprint"):
                st.caption(f"Signature `{hdc_src['fingerprint'][:16]}…` · "
                           f"history size {hdc_src.get('history_size', 0)} · dim {hdc_src.get('dim', '—')}")
            matches = (near or {}).get("matches") or []
            if not matches:
                st.info("No prior epochs to compare yet — record more resonance cycles.")
            else:
                for m in matches:
                    sim = m.get("similarity", 0)
                    bar = "▰" * int(round(sim * 10)) + "▱" * (10 - int(round(sim * 10)))
                    st.write(f"`{m['epoch_id']}`")
                    st.markdown(
                        f"<span style='color:#9b59b6'>{bar}</span> &nbsp; {sim:.3f}",
                        unsafe_allow_html=True,
                    )

    if action_result:
        with st.expander("Last action result"):
            st.json(action_result)

# ═══════════════════════════════════════════════════════════════
elif page == "ODL Brain":
    st.header("ODL Brain")
    st.caption("Knowledge map × value dimensions × coupling — browser lens on server-side resonance.")

    render_coverage_banner((brain_data or {}).get("coverage"))

    tab_dims, tab_map, tab_coupling, tab_memory = st.tabs(
        ["Dimension Studio", "Knowledge Map", "Coupling & Resonance", "Epoch Memory"]
    )

    dimensions = (dims_data or brain_data or {}).get("dimensions") or []
    coupling = (dims_data or brain_data or {}).get("coupling") or {}

    with tab_dims:
        st.subheader("Dimension Studio")
        st.caption("Edits save to `configs/odl_dimensions.yaml` and apply on the next resonance cycle.")
        if not dimensions:
            st.warning("Could not load dimensions.")
        else:
            for d in dimensions:
                with st.expander(f"{d.get('label')} (`{d.get('id')}`)", expanded=False):
                    c1, c2, c3 = st.columns(3)
                    new_target = c1.number_input("Target", 0.0, 1.0, float(d.get("target", 0.7)), key=f"t_{d['id']}")
                    new_weight = c2.number_input("Weight", 0.1, 3.0, float(d.get("weight", 1.0)), key=f"w_{d['id']}")
                    new_floor = c3.number_input("Floor", 0.0, 1.0, float(d.get("floor", 0.4)), key=f"f_{d['id']}")
                    new_proxy = st.text_input("Proxy / signal", d.get("proxy", ""), key=f"p_{d['id']}")
                    sm = d.get("signal_map") or {}
                    st.caption(f"Trinity pillar: **{d.get('trinity_pillar')}** · Patterns: `{sm.get('path_patterns', [])}`")

            if st.button("Save dimension overrides", type="primary"):
                overrides = {}
                for d in dimensions:
                    did = d["id"]
                    overrides[did] = {
                        "target": st.session_state.get(f"t_{did}"),
                        "weight": st.session_state.get(f"w_{did}"),
                        "floor": st.session_state.get(f"f_{did}"),
                        "proxy": st.session_state.get(f"p_{did}"),
                    }
                if api_ok:
                    resp = api_put("/odl/dimensions", {"overrides": overrides})
                    if resp:
                        st.success(f"Saved → {resp.get('saved', 'config')}")
                        st.rerun()
                else:
                    from src.odl.dimension_config import apply_overrides
                    out = apply_overrides(overrides)
                    st.success(f"Saved locally → {out.get('saved')}")

    with tab_map:
        st.subheader("Knowledge Map (Trinity × Dimensions)")
        col_f1, col_f2, col_f3 = st.columns(3)
        proj = col_f1.selectbox(
            "Project filter",
            ["", "qm2arl", "tradeproto", "telpai", "dragon-seal", "ghi", "documents"],
        )
        search_q = col_f2.text_input("Search nodes", placeholder="odl, compliance, rwa…")
        node_limit = col_f3.slider("Max nodes", 30, 200, 100)
        graph_path = f"/odl/brain/graph?limit={node_limit}"
        if proj:
            graph_path += f"&project={proj}"
        if search_q:
            import urllib.parse
            graph_path += f"&q={urllib.parse.quote(search_q)}"

        graph = api_get(graph_path, timeout=20) if api_ok else None
        if not graph and not api_ok:
            from src.odl.brain import build_brain_graph
            graph = build_brain_graph(project=proj or None, limit=node_limit, search=search_q or None)

        if graph and graph.get("error"):
            st.error(graph["error"])
        elif graph:
            counts = graph.get("dimension_counts") or {}
            cc = st.columns(6)
            for i, dim_id in enumerate(DIM_COLORS):
                with cc[i % 6]:
                    st.metric(dim_id.title(), counts.get(dim_id, 0))
            plot_brain_graph(graph)

    with tab_coupling:
        st.subheader("Dimension coupling heatmap")
        st.caption("Cross-dimension tensions and reinforcements (from `odl_dimensions.yaml`).")
        plot_coupling_heatmap(coupling)
        if res_data and res_data.get("resonance"):
            r = res_data["resonance"]
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("R", f"{r.get('system_resonance', 0):.3f}")
            c2.metric("ρ phase", f"{r.get('phase_coherence', 0):.3f}")
            c3.metric("Q quantum", f"{r.get('quantum_coherence', 0):.3f}")
            c4.metric("Verdict", r.get("verdict", "—"))

    with tab_memory:
        st.subheader("Epoch memory (high-resonance ledger)")
        if ledger_data and ledger_data.get("epochs"):
            top = sorted(
                ledger_data["epochs"],
                key=lambda e: (e.get("resonance") or {}).get("system_resonance", 0),
                reverse=True,
            )[:8]
            for e in top:
                res = e.get("resonance") or {}
                st.write(
                    f"**{e.get('epoch_id')}** — R={res.get('system_resonance', 0):.3f} "
                    f"[{res.get('verdict')}] · coverage {res.get('coverage', {}).get('coverage_pct')}%"
                )
        else:
            st.info("Run a resonance cycle to populate epoch memory.")

# ═══════════════════════════════════════════════════════════════
elif page == "Ledger Explorer":
    st.header("Ledger Explorer")

    if not ledger_data:
        st.warning("Could not load ledger.")
    else:
        chain = ledger_data.get("chain") or {}
        valid = chain.get("valid", False)
        st.metric("Chain height", ledger_data.get("height", 0))
        if valid:
            st.success(f"Chain integrity: **VALID** (head `{str(chain.get('head', ''))[:16]}…`)")
        else:
            st.error(f"Chain **BROKEN** at index {chain.get('broken_at')} — {chain.get('reason')}")

        epochs = ledger_data.get("epochs") or []
        if epochs:
            rows = []
            for e in epochs:
                res = e.get("resonance") or {}
                gov = e.get("governance") or {}
                anc = e.get("anchor") or {}
                rows.append({
                    "epoch_id": e.get("epoch_id"),
                    "index": e.get("index"),
                    "timestamp": (e.get("timestamp_utc") or "")[:19],
                    "R": round(res.get("system_resonance", 0), 3),
                    "verdict": res.get("verdict"),
                    "governor": gov.get("decision"),
                    "coverage_pct": res.get("coverage", {}).get("coverage_pct"),
                    "anchored": anc.get("status") == "ANCHORED",
                    "sha256": (e.get("sha256") or "")[:12] + "…",
                })
            st.dataframe(rows, use_container_width=True, hide_index=True)

            st.subheader("Epoch detail")
            ids = [e.get("epoch_id") for e in epochs]
            pick = st.selectbox("Select epoch", ids, index=0)
            detail = next((e for e in epochs if e.get("epoch_id") == pick), None)
            if detail:
                st.json(detail)
                if detail.get("verify_url"):
                    st.link_button("Verify on Dragon Seal", detail["verify_url"])

# ═══════════════════════════════════════════════════════════════
else:
    st.header("Framework Status")

    if not framework_data:
        try:
            from src.odl.nodes import load_manifest, summarize
            framework_data = summarize(load_manifest())
        except Exception as e:
            st.error(f"Could not load framework manifest: {e}")
            framework_data = None

    if framework_data:
        overall = framework_data.get("overall_build_completion_pct", 0)
        st.metric("Overall build completion", f"{overall:.1f}%")
        st.progress(min(1.0, overall / 100.0))

        layers = framework_data.get("layers") or []
        if layers:
            st.subheader("By layer")
            for layer in layers:
                pct = layer.get("completion_pct", 0)
                st.write(f"**{layer.get('name')}** — {pct:.0f}%")
                st.progress(min(1.0, pct / 100.0))

        nodes = framework_data.get("node_types") or {}
        st.subheader("Node inventory")
        for status in ("operational", "partial", "to_build"):
            items = nodes.get(status) or []
            if items:
                st.write(f"_{status}_: {', '.join(items)}")

        cost = framework_data.get("cost_rollup") or {}
        if cost:
            st.subheader("Cost rollup (AACE Class 5)")
            st.write(
                f"Monthly OpEx **${cost.get('monthly_opex_expected_usd', 0):,.0f}** "
                f"(${cost.get('monthly_opex_low_usd', 0):,.0f}–${cost.get('monthly_opex_high_usd', 0):,.0f})"
            )
            st.write(
                f"CapEx **${cost.get('capex_expected_usd', 0):,.0f}** "
                f"(${cost.get('capex_low_usd', 0):,.0f}–${cost.get('capex_high_usd', 0):,.0f})"
            )

        with st.expander("Full manifest rollup (JSON)"):
            st.json(framework_data)