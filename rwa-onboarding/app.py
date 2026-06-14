"""
TELPAI-Q × RWA Onboarding Console — one platform to onboard, verify, classify,
seal, and gate in-ground real-world assets (natural gas and gold).

Run:
    streamlit run rwa-onboarding/app.py --server.port 8510

Pipeline (commodity-agnostic spine in src/telpai_rwa/onboarding.py):
    intake → TELPAI survey → TELPAI-Q quantum verify → classify (PRMS|NI 43-101)
           → QRE/QP package → oracle epoch → Dragon Seal → Reg D 506 gate
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.telpai_rwa import onboard_asset  # noqa: E402

GAS_EXAMPLE = ROOT / "configs" / "rwa_rivers_bend_gas.example.json"
GOLD_EXAMPLE = ROOT / "configs" / "rwa_gold_mine_ni43101.example.json"

st.set_page_config(page_title="TELPAI-Q · RWA Onboarding", page_icon="🛢️", layout="wide")

st.title("TELPAI-Q · RWA Onboarding Console")
st.caption(
    "One platform — onboard, quantum-verify, classify, seal, and gate in-ground "
    "real-world assets. Gas via SPE-PRMS · Gold via NI 43-101 / CIM."
)


def _load(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


with st.sidebar:
    st.header("1 · Asset intake")
    commodity = st.radio("Commodity", ["Natural gas (SPE-PRMS)", "Gold (NI 43-101)"])
    is_gold = commodity.startswith("Gold")

    if st.button("Load example asset", use_container_width=True):
        st.session_state["asset_json"] = json.dumps(
            _load(GOLD_EXAMPLE if is_gold else GAS_EXAMPLE), indent=2
        )

    default_json = st.session_state.get(
        "asset_json", json.dumps(_load(GOLD_EXAMPLE if is_gold else GAS_EXAMPLE), indent=2)
    )
    asset_text = st.text_area("Asset record (JSON)", value=default_json, height=320)

    st.divider()
    st.header("2 · TELPAI-Q backend")
    backend = st.selectbox(
        "Quantum backend",
        ["default.qubit (local sim)", "lightning.qubit", "bluequbit.cpu", "bluequbit.gpu"],
    )
    backend_val = "" if backend.startswith("default") else backend.split()[0]
    has_token = bool(os.environ.get("BLUEQUBIT_API_TOKEN"))
    if backend_val.startswith("bluequbit") and not has_token:
        st.warning("BLUEQUBIT_API_TOKEN not set — will fall back to local simulator.")

    st.divider()
    st.header("3 · Seal & permanence")
    do_seal = st.checkbox("Dragon Seal the oracle epoch", value=True)
    do_pin = st.checkbox("Pin to Lighthouse (IPFS)", value=False)
    if do_pin and not os.environ.get("LIGHTHOUSE_API_KEY"):
        st.warning("LIGHTHOUSE_API_KEY not set — bundle will be written locally only.")

    run = st.button("Run onboarding pipeline", type="primary", use_container_width=True)


if run:
    try:
        asset = json.loads(asset_text)
    except json.JSONDecodeError as e:
        st.error(f"Invalid asset JSON: {e}")
        st.stop()

    with st.spinner("Running TELPAI survey → quantum verify → classify → seal → gate…"):
        result = onboard_asset(
            asset,
            vqc_backend=backend_val,
            seal=do_seal,
            pin_to_lighthouse=do_pin,
            persist=True,
        )
    st.session_state["result"] = result

result = st.session_state.get("result")
if not result:
    st.info("Configure an asset in the sidebar and click **Run onboarding pipeline**.")
    st.stop()

# ── Top-line metrics ──────────────────────────────────────────────────────
v = result["quantum_verification"]
clf = result["classification"]
gate = result["securities_gate"]

aia = result.get("ai_audit")
aia_div = result.get("ai_audit_division")
audit_tab_label = f"Division {aia_div} AI audit" if aia_div else "AI audit"

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Commodity", result["commodity"], help=f"Expert sign-off: {result['expert_required']}")
c2.metric("TELPAI-Q verification", f"{v['verification_score']:.2f}", v["confidence_band"].upper())
c3.metric("Classification", clf.get("category", "—"),
          "tokenizable" if clf.get("tokenizable") else "not primary-tokenizable")
if aia:
    c4.metric(f"Div {aia_div} AI audit", f"{aia['overall_audit_pct']:.0f}%",
              "PASS" if aia["audit_gate_passed"] else "BLOCKED")
else:
    c4.metric("AI audit", "n/a")
c5.metric("Reg D gate", "READY" if gate["ready"] else "BLOCKED", f"{gate['score_pct']:.0f}% complete")

tabs = st.tabs(
    ["Quantum verify", "Classification", audit_tab_label, "Volumes",
     "Oracle epoch", "Dragon Seal", "Securities gate", "Next steps"]
)

with tabs[0]:
    st.subheader("TELPAI-Q geospatial verification")
    st.write(f"**Backend:** `{v['backend']}` · **Quantum hardware:** {v['quantum_hardware']}")
    st.write(f"**Anomaly score:** {v['anomaly_score']:.3f} · **Reference set:** {v['reference_set_size']}")
    labels = ["seismic", "magnetics", "gravity", "volumetric/analog",
              "thermal/flares", "lease ctx", "seepage", "data quality"]
    fv = v["feature_vector"]
    st.bar_chart({"signature": dict(zip(labels, fv))})
    for n in v.get("notes", []):
        st.caption("• " + n)

with tabs[1]:
    st.subheader("Resource / reserve classification")
    st.json(clf)

with tabs[2]:
    if not aia:
        st.info("No AI audit division applies to this asset.")
    else:
        st.subheader(f"Division {aia['division']} — AI audit agents")
        st.caption(aia.get("framework", ""))
        st.write(
            f"**Overall:** {aia['overall_audit_pct']:.0f}% · "
            f"**{aia['audit_status']}** · "
            f"trained on {aia.get('training_episodes', '—')} episodes"
        )
        if aia["audit_gate_passed"]:
            st.success("AI audit gate PASSED — agents conform across critical domains.")
        elif not aia.get("trained"):
            st.warning("Agents not yet trained — run the audit config below to generate scores.")
        else:
            st.error(
                f"AI audit gate BLOCKED — binding domain "
                f"`{aia['binding_domain']}` at {aia['binding_domain_pct']}%."
            )
        if aia.get("blocker"):
            st.warning(f"Blocker: {aia['blocker']}")

        rows = {}
        for dd in aia["domains"]:
            label = f"{dd['agent']} · {dd['domain']}"
            rows[label] = dd["combined_pct"]
        st.bar_chart({"audit %": rows})

        st.dataframe(
            [
                {
                    "agent": dd["agent"],
                    "domain": dd["domain"],
                    "role": dd["role"],
                    "trained %": dd["trained_audit_pct"],
                    "asset %": dd["asset_agent_score_pct"],
                    "combined %": dd["combined_pct"],
                    "status": dd["trained_status"],
                }
                for dd in aia["domains"]
            ],
            use_container_width=True,
        )
        st.caption(aia["recommendation"])
        st.code(aia["run_command"], language="bash")

with tabs[3]:
    st.subheader("Probabilistic volumes")
    st.json(result["volumes"])

with tabs[4]:
    st.subheader("Oracle epoch (sealed body)")
    epoch = result["oracle_epoch"]
    st.code(f"SHA-256: {epoch.get('sha256')}")
    st.write(f"Verify URL: {epoch.get('dragon_seal', {}).get('verify_url', '—')}")
    st.json(epoch)

with tabs[5]:
    st.subheader("Dragon Seal")
    seal = result.get("dragon_seal")
    if not seal:
        st.info("Sealing was disabled for this run.")
    else:
        st.write(f"**Seal ID:** `{seal['seal_id']}`")
        st.write(f"**Status:** {seal['status']}")
        st.write(f"**Verify URL:** {seal['verify_url']}")
        st.write(f"**Bundle:** `{seal['dragon_path']}`")
        if seal.get("ipfs_cid"):
            st.success(f"Pinned to IPFS: {seal['ipfs_cid']}")
            st.write(seal.get("gateway_url"))
        if seal.get("pin_error"):
            st.warning(seal["pin_error"])

with tabs[6]:
    st.subheader(f"SEC Reg D {gate['rule']} gate")
    st.write("**Ready:**", gate["ready"], f"· {gate['score_pct']:.0f}% checklist complete")
    if gate.get("ai_audit_passed") is not None:
        st.write(f"**Division {gate.get('ai_audit_division')} AI audit passed:**", gate["ai_audit_passed"])
    if gate["missing"]:
        st.write("**Missing:**", ", ".join(gate["missing"]))
    for b in gate["blockers"]:
        st.warning(b)

with tabs[7]:
    st.subheader("Next steps")
    for i, s in enumerate(result["next_steps"], 1):
        st.write(f"{i}. {s}")

st.divider()
st.download_button(
    "Download full onboarding result (JSON)",
    data=json.dumps(result, indent=2, default=str),
    file_name=f"{result['asset_id']}_onboarding.json",
    mime="application/json",
)
