"""
Green Horizon Innovation — QM2ARL Command Center
Streamlit app with live FastAPI integration and GQ (Grok Quantum) Live Brain.
Run: streamlit run app_geophysical_demo.py
Requires: FastAPI backend running on port 8000 (uvicorn api_server:app --port 8000)
"""
from __future__ import annotations

from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import requests
import json

API_BASE = "http://localhost:8000"


# ─── Helper: Fetch from FastAPI with fallback ───

def api_get(endpoint: str, fallback=None):
    """GET from FastAPI backend; return fallback on failure."""
    try:
        resp = requests.get(f"{API_BASE}{endpoint}", timeout=5)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return fallback


def api_post(endpoint: str, data: dict, fallback=None):
    """POST to FastAPI backend; return fallback on failure."""
    try:
        resp = requests.post(f"{API_BASE}{endpoint}", json=data, timeout=30)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return fallback


# ─── Inline ENGRAM-ENGN (demo fallback) ───

class ENGRAMENGN:
    def __init__(self, memory_capacity: int = 1000, prune_threshold: float = 0.5):
        self.memory_capacity = memory_capacity
        self.prune_threshold = prune_threshold
        self.memory_buffer: list[tuple[Any, Any, float, Any, float]] = []
        self.prune_count = 0

    def add_memory(self, state, action, reward, next_state, hmu):
        self.memory_buffer.append((state, action, reward, next_state, hmu))
        if len(self.memory_buffer) > self.memory_capacity:
            self.prune()

    def prune(self):
        if not self.memory_buffer:
            return
        sorted_mem = sorted(self.memory_buffer, key=lambda x: x[4])
        keep_num = int(self.memory_capacity * 0.8)
        self.memory_buffer = sorted_mem[-keep_num:]
        self.prune_count += 1

    def refresh_context(self):
        return self.memory_buffer[-10:]


# ─── Synthetic 4D anomaly field ───

def build_anomaly_field(nx: int, ny: int, n_time: int, seed: int = 42) -> np.ndarray:
    np.random.seed(seed)
    field = np.zeros((ny, nx, n_time))
    for _ in range(4):
        cx = np.random.randint(nx // 4, 3 * nx // 4)
        cy = np.random.randint(ny // 4, 3 * ny // 4)
        sigma = 8 + np.random.rand() * 8
        drift_x = (np.random.rand() - 0.5) * 0.5
        drift_y = (np.random.rand() - 0.5) * 0.5
        amp = 0.5 + np.random.rand() * 0.5
        for t in range(n_time):
            xt = cx + drift_x * t
            yt = cy + drift_y * t
            x = np.linspace(0, nx - 1, nx)
            y = np.linspace(0, ny - 1, ny)
            xx, yy = np.meshgrid(x, y)
            field[:, :, t] += amp * np.exp(-((xx - xt) ** 2 + (yy - yt) ** 2) / (2 * sigma ** 2))
    field = (field - field.min()) / max(field.max() - field.min(), 1e-9)
    return field


# ─── Harmony metric ───

def compute_hmu(field_value: float, target: float = 0.5, omega: float = 1.0, n_extract: int = 0, n_agents: int = 1) -> float:
    R_c = max(0.0, 1.0 - abs(field_value - target))
    A_n = 1.0 - (n_extract / max(n_agents, 1))
    return 0.8 * R_c + 0.1 * A_n + 0.1 * omega


# ═══════════════════════════════════════════
#  PAGE CONFIG
# ═══════════════════════════════════════════

st.set_page_config(
    page_title="GQ Command Center — QM2ARL · Green Horizon",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ═══════════════════════════════════════════
#  HOLOGRAPHIC THEME — Matches GHI QM2ARL Section
# ═══════════════════════════════════════════
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;500;600;700;900&family=JetBrains+Mono:wght@300;400;500&display=swap');

/* ─── Global Background ─── */
.stApp {
    background: #020609;
    color: #eaf0ff;
}
[data-testid="stHeader"] {
    background: rgba(2,6,9,0.95);
    border-bottom: 1px solid rgba(0,200,150,0.16);
}

/* ─── Sidebar ─── */
[data-testid="stSidebar"] {
    background: rgba(6,10,18,0.95);
    border-right: 1px solid rgba(0,200,150,0.16);
}
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3,
[data-testid="stSidebar"] .stMarkdown h1, [data-testid="stSidebar"] .stMarkdown h2 {
    font-family: 'Orbitron', sans-serif;
    color: #00c896;
    letter-spacing: 0.12em;
    font-size: 0.85rem;
}
[data-testid="stSidebar"] label {
    font-family: 'Orbitron', sans-serif !important;
    font-size: 0.55rem !important;
    letter-spacing: 0.18em !important;
    color: #00e5ff !important;
}

/* ─── Slider Holographic ─── */
[data-testid="stSlider"] > div > div > div > div {
    background: linear-gradient(90deg, #00c896, #00e5ff) !important;
}
[data-testid="stSlider"] [role="slider"] {
    background: #00e5ff !important;
    box-shadow: 0 0 12px rgba(0,229,255,0.5) !important;
    border: 2px solid rgba(0,229,255,0.6) !important;
}
.stSlider p {
    font-family: 'JetBrains Mono', monospace !important;
    color: #00c896 !important;
    font-size: 0.7rem !important;
}

/* ─── Headings ─── */
h1, h2, h3 {
    font-family: 'Orbitron', sans-serif !important;
    letter-spacing: 0.08em;
}
h1 {
    color: #eaf0ff !important;
    text-shadow: 0 0 20px rgba(0,229,255,0.3);
}
h2, h3 {
    color: #00e5ff !important;
}

/* ─── Tabs ─── */
[data-testid="stTabs"] button {
    font-family: 'Orbitron', sans-serif !important;
    font-size: 0.6rem !important;
    letter-spacing: 0.14em !important;
    color: #8892b0 !important;
    border: 1px solid transparent !important;
    border-radius: 12px !important;
    padding: 10px 20px !important;
    transition: all 0.3s !important;
    background: none !important;
}
[data-testid="stTabs"] button:hover {
    color: #00e5ff !important;
    border-color: rgba(0,229,255,0.2) !important;
    background: rgba(0,229,255,0.05) !important;
}
[data-testid="stTabs"] button[aria-selected="true"] {
    color: #00e5ff !important;
    background: rgba(0,229,255,0.08) !important;
    border-color: rgba(0,229,255,0.3) !important;
    box-shadow: 0 0 20px rgba(0,229,255,0.08) !important;
}
[data-testid="stTabs"] [role="tablist"] {
    background: rgba(6,10,18,0.7);
    border: 1px solid rgba(0,229,255,0.12);
    border-radius: 16px;
    padding: 6px;
    gap: 4px;
}

/* ─── Metrics ─── */
[data-testid="stMetric"] {
    background: rgba(6,10,18,0.88) !important;
    border: 1px solid rgba(0,200,150,0.16) !important;
    border-radius: 14px !important;
    padding: 16px !important;
    position: relative;
    overflow: hidden;
}
[data-testid="stMetric"]::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg, transparent, #00c896, transparent);
}
[data-testid="stMetric"] [data-testid="stMetricValue"] {
    font-family: 'Orbitron', sans-serif !important;
    color: #00c896 !important;
    font-size: 1.4rem !important;
}
[data-testid="stMetric"] [data-testid="stMetricLabel"] {
    font-family: 'JetBrains Mono', monospace !important;
    letter-spacing: 0.12em !important;
    color: #8892b0 !important;
    font-size: 0.55rem !important;
}
[data-testid="stMetric"] [data-testid="stMetricDelta"] {
    font-family: 'JetBrains Mono', monospace !important;
    color: #00e5ff !important;
}

/* ─── Buttons ─── */
.stButton button {
    font-family: 'Orbitron', sans-serif !important;
    font-size: 0.6rem !important;
    letter-spacing: 0.2em !important;
    background: linear-gradient(135deg, rgba(0,200,150,0.15), rgba(0,229,255,0.10)) !important;
    border: 1px solid rgba(0,200,150,0.35) !important;
    color: #00c896 !important;
    border-radius: 12px !important;
    padding: 10px 24px !important;
    transition: all 0.3s !important;
}
.stButton button:hover {
    background: linear-gradient(135deg, rgba(0,200,150,0.25), rgba(0,229,255,0.18)) !important;
    box-shadow: 0 0 25px rgba(0,200,150,0.15) !important;
    border-color: rgba(0,200,150,0.5) !important;
    transform: translateY(-1px);
}
.stButton button[kind="primary"] {
    background: linear-gradient(135deg, rgba(0,229,255,0.20), rgba(0,200,150,0.15)) !important;
    border-color: rgba(0,229,255,0.45) !important;
    color: #00e5ff !important;
}

/* ─── Text Input ─── */
.stTextInput input {
    font-family: 'JetBrains Mono', monospace !important;
    background: rgba(0,229,255,0.03) !important;
    border: 1px solid rgba(0,229,255,0.18) !important;
    border-radius: 10px !important;
    color: #eaf0ff !important;
    caret-color: #00e5ff !important;
}
.stTextInput input:focus {
    border-color: rgba(0,229,255,0.45) !important;
    box-shadow: 0 0 15px rgba(0,229,255,0.1) !important;
}
.stTextInput label {
    font-family: 'Orbitron', sans-serif !important;
    font-size: 0.6rem !important;
    letter-spacing: 0.15em !important;
    color: #00c896 !important;
}

/* ─── Alerts ─── */
[data-testid="stAlert"] {
    background: rgba(6,10,18,0.88) !important;
    border-radius: 12px !important;
    font-family: 'JetBrains Mono', monospace !important;
}

/* ─── Dividers ─── */
hr {
    border-color: rgba(0,200,150,0.12) !important;
}

/* ─── Charts ─── */
[data-testid="stPlotlyChart"], .stPlotlyChart {
    border: 1px solid rgba(0,229,255,0.10);
    border-radius: 16px;
    overflow: hidden;
}

/* ─── Captions & Body Text ─── */
.stCaption, .stMarkdown p {
    font-family: 'JetBrains Mono', monospace;
    color: #8892b0;
    font-size: 0.72rem;
}

/* ─── Progress Bar ─── */
.stProgress > div > div > div {
    background: linear-gradient(90deg, #00c896, #00e5ff) !important;
}

/* ─── Success/Warning/Info Alerts ─── */
.stSuccess {
    background: rgba(0,200,150,0.08) !important;
    border: 1px solid rgba(0,200,150,0.25) !important;
    color: #00c896 !important;
}
.stWarning {
    background: rgba(200,168,75,0.08) !important;
    border: 1px solid rgba(200,168,75,0.25) !important;
}

/* ─── GQ Chat Messages ─── */
.stContainer {
    border-left: 2px solid rgba(0,229,255,0.1);
    padding-left: 12px;
    margin-bottom: 8px;
}
</style>
""", unsafe_allow_html=True)

# ─── Check API status ───
api_health = api_get("/health")
api_online = api_health is not None

# ─── Header ───
col_h1, col_h2 = st.columns([3, 1])
with col_h1:
    st.title("🧠 GQ COMMAND CENTER")
    st.markdown("**Green Horizon Innovation · QM2ARL + ENGRAM-ENGN · TELPAI-QUANTUM**")
with col_h2:
    if api_online:
        st.success(f"🟢 GQ API Online")
        if api_health.get("grok_configured"):
            st.caption("Grok Quantum: ACTIVE")
        else:
            st.caption("Grok Quantum: OFFLINE MODE")
    else:
        st.warning("🔴 GQ API Offline — using demo data")
        st.caption("Start: uvicorn api_server:app --port 8000")

st.divider()

# ─── Tabs ───
tab_gq, tab_field, tab_agents, tab_trajectory, tab_inventory = st.tabs([
    "🧠 GQ Live Brain",
    "🌍 4D Field",
    "⚡ Agent Scores",
    "📈 3D Trajectory",
    "📦 Inventory",
])

# ─── Sidebar ───
with st.sidebar:
    st.header("Parameters")
    nx = st.slider("Grid width", 20, 80, 50)
    ny = st.slider("Grid height", 20, 80, 50)
    n_time = st.slider("Time steps", 10, 60, 30)
    n_agents = st.slider("Agents", 2, 8, 4)
    memory_capacity = st.slider("ENGRAM capacity", 100, 2000, 500)
    n_sim_steps = st.slider("Simulation steps", 20, 200, 80)

    st.divider()
    st.subheader("API Status")
    if api_online:
        st.success("FastAPI: Connected")
        st.caption(f"Training data: {'✓' if api_health.get('has_training_data') else '✗'}")
        st.caption(f"Grok: {'✓ Active' if api_health.get('grok_configured') else '✗ Offline'}")
    else:
        st.error("FastAPI: Disconnected")

    if st.button("Reset field & simulation"):
        for key in ["field", "sim_log", "engrams"]:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()


# ═══════════════════════════════════════════
#  TAB 1: GQ LIVE BRAIN
# ═══════════════════════════════════════════

with tab_gq:
    st.subheader("🧠 Ask GQ — Grok Quantum Live Brain")
    st.markdown(
        "GQ is the intelligent core of the QM2ARL system. Ask questions about training performance, "
        "agent behavior, resource trajectories, or geophysical anomaly detection strategy."
    )

    # Chat history
    if "gq_history" not in st.session_state:
        st.session_state["gq_history"] = []

    # Input
    user_question = st.text_input(
        "Ask GQ anything:",
        placeholder="e.g. What is the current resource level? How are agents performing? Suggest next training config.",
        key="gq_input",
    )

    col_ask, col_clear = st.columns([1, 4])
    with col_ask:
        ask_clicked = st.button("🧠 Ask GQ", type="primary", use_container_width=True)
    with col_clear:
        if st.button("Clear history"):
            st.session_state["gq_history"] = []
            st.rerun()

    if ask_clicked and user_question:
        with st.spinner("GQ is thinking..."):
            if api_online:
                result = api_post("/gq/query", {"question": user_question, "context": "qm2arl_geophysical"})
                if result:
                    answer = result.get("answer", "No response")
                    model = result.get("model", "unknown")
                else:
                    answer = "Failed to reach GQ API."
                    model = "error"
            else:
                answer = (
                    f"GQ is offline (FastAPI not running). Your question: '{user_question}'\n\n"
                    "To enable GQ:\n"
                    "1. cd ~/QM2ARL\n"
                    "2. source .venv/bin/activate\n"
                    "3. uvicorn api_server:app --port 8000"
                )
                model = "offline"

            st.session_state["gq_history"].append({
                "question": user_question,
                "answer": answer,
                "model": model,
            })

    # Display chat history
    for i, entry in enumerate(reversed(st.session_state["gq_history"])):
        with st.container():
            st.markdown(f"**You:** {entry['question']}")
            st.markdown(f"**GQ ({entry['model']}):** {entry['answer']}")
            st.divider()

    # Quick action buttons
    st.subheader("Quick Queries")
    qcol1, qcol2, qcol3, qcol4 = st.columns(4)
    with qcol1:
        if st.button("📊 Training Status"):
            st.session_state["gq_input"] = "What is the current training status and resource level?"
            st.rerun()
    with qcol2:
        if st.button("🎯 Agent Performance"):
            st.session_state["gq_input"] = "How are the QM2ARL agents performing? Which agent has the highest Hmu?"
            st.rerun()
    with qcol3:
        if st.button("🔧 Config Suggestion"):
            st.session_state["gq_input"] = "Based on current metrics, what config changes would improve convergence?"
            st.rerun()
    with qcol4:
        if st.button("🌍 Anomaly Analysis"):
            st.session_state["gq_input"] = "Analyze the geophysical anomaly field and suggest high-value exploration targets."
            st.rerun()


# ═══════════════════════════════════════════
#  TAB 2: 4D ANOMALY FIELD
# ═══════════════════════════════════════════

with tab_field:
    st.subheader("Interactive 4D Anomaly Field")

    if "field" not in st.session_state:
        st.session_state["field"] = build_anomaly_field(nx, ny, n_time)
    field = st.session_state["field"]
    if field.shape[0] != ny or field.shape[1] != nx or field.shape[2] != n_time:
        st.session_state["field"] = build_anomaly_field(nx, ny, n_time)
        field = st.session_state["field"]

    time_idx = st.slider("Time", 0, field.shape[2] - 1, 0, key="time_slider")
    slice_2d = field[:, :, time_idx]

    fig, ax = plt.subplots(figsize=(8, 6))
    im = ax.imshow(slice_2d, cmap="hot", aspect="auto", origin="lower", vmin=0, vmax=1)
    ax.set_title(f"Anomaly intensity (time step {time_idx})")
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    plt.colorbar(im, ax=ax, label="Intensity")
    st.pyplot(fig)
    plt.close(fig)
    st.caption("Time-varying holographic field: high intensity = candidate anomaly (mineral, geothermal).")


# ═══════════════════════════════════════════
#  TAB 3: AGENT SCORES (live from API)
# ═══════════════════════════════════════════

with tab_agents:
    st.subheader("QM2ARL Agent Performance")

    if api_online:
        scores_data = api_get("/agent-scores")
        if scores_data and "agents" in scores_data:
            source = scores_data.get("source", "unknown")
            st.caption(f"Data source: {source}")
            agents_list = scores_data["agents"]

            cols = st.columns(min(len(agents_list), 4))
            for i, agent in enumerate(agents_list):
                with cols[i % len(cols)]:
                    st.metric(f"Agent {agent['id']} — Hμ", f"{agent['hmu']:.3f}")
                    st.metric(f"Mean Reward", f"{agent['mean_reward']:.3f}")
                    st.caption(f"E:{agent['extracts']} I:{agent['invests']} X:{agent['explores']}")

        elif scores_data and "metrics" in scores_data:
            st.json(scores_data["metrics"])
        else:
            st.info("No agent score data available.")
    else:
        st.info("API offline — running local simulation for agent scores.")

    # Local simulation fallback
    st.subheader("Local QM2ARL Simulation")

    if "sim_log" not in st.session_state:
        st.session_state["sim_log"] = {"step": [], "hmu": [], "reward": [], "buffer_size": [], "prunes": []}
    if "engrams" not in st.session_state or len(st.session_state["engrams"]) != n_agents:
        st.session_state["engrams"] = [ENGRAMENGN(memory_capacity=memory_capacity) for _ in range(n_agents)]

    engrams = st.session_state["engrams"]
    sim_log = st.session_state["sim_log"]

    if st.button("Run simulation", key="run_sim"):
        sim_log = {"step": [], "hmu": [], "reward": [], "buffer_size": [], "prunes": []}
        progress = st.progress(0)
        for step in range(n_sim_steps):
            t = step % field.shape[2]
            slice_t = field[:, :, t]
            step_rewards = []
            step_hmus = []
            for i in range(n_agents):
                xi = np.random.randint(0, slice_t.shape[1])
                yi = np.random.randint(0, slice_t.shape[0])
                val = float(slice_t[yi, xi])
                reward = val
                hmu = compute_hmu(val, target=0.5, n_extract=0, n_agents=n_agents)
                state = np.array([xi / max(slice_t.shape[1], 1), yi / max(slice_t.shape[0], 1), t / max(field.shape[2], 1)])
                action = np.random.randint(0, 3)
                next_state = state + 0.01 * np.random.randn(3)
                engrams[i].add_memory(state, action, reward, next_state, hmu)
                step_rewards.append(reward)
                step_hmus.append(hmu)
            sim_log["step"].append(step)
            sim_log["hmu"].append(np.mean(step_hmus))
            sim_log["reward"].append(np.mean(step_rewards))
            sim_log["buffer_size"].append(sum(len(e.memory_buffer) for e in engrams))
            sim_log["prunes"].append(sum(e.prune_count for e in engrams))
            progress.progress((step + 1) / n_sim_steps)
        progress.empty()
        st.session_state["sim_log"] = sim_log
        st.rerun()

    if sim_log["step"]:
        col1, col2 = st.columns(2)
        with col1:
            st.line_chart({"Hμ (harmony)": sim_log["hmu"], "Reward": sim_log["reward"]})
        with col2:
            st.line_chart({"ENGRAM buffer size": sim_log["buffer_size"], "Total prunes": sim_log["prunes"]})

    # ENGRAM stats
    st.subheader("ENGRAM-ENGN Pruning Stats")
    if engrams:
        ecols = st.columns(min(n_agents, 4))
        for i, e in enumerate(engrams):
            with ecols[i % len(ecols)]:
                st.metric(f"Agent {i} buffer", len(e.memory_buffer), f"prunes: {e.prune_count}")

    # Hmu dashboard
    st.subheader("Harmony Metric (Hμ) Dashboard")
    if sim_log["hmu"]:
        avg_hmu = np.mean(sim_log["hmu"])
        st.metric("Mean Hμ (session)", f"{avg_hmu:.3f}", "0.8·R_c + 0.1·A_n + 0.1·Ω")
    else:
        st.metric("Mean Hμ (session)", "—", "Run simulation to populate")


# ═══════════════════════════════════════════
#  TAB 4: 3D RESOURCE TRAJECTORY (live)
# ═══════════════════════════════════════════

with tab_trajectory:
    st.subheader("Hyperscale 3D Resource Trajectory")

    # Try live API first
    traj_data = api_get("/trajectory") if api_online else None

    if traj_data and traj_data.get("trajectory"):
        resource_demo = np.array(traj_data["trajectory"])
        st.success(f"✓ Live data from QM2ARL training — {traj_data['steps']} steps")
        mcol1, mcol2, mcol3 = st.columns(3)
        with mcol1:
            st.metric("Current", f"{traj_data['trajectory'][-1]:.1f}")
        with mcol2:
            st.metric("Peak", f"{traj_data['max']:.1f}")
        with mcol3:
            st.metric("Mean", f"{traj_data['mean']:.1f}")
    else:
        # Fallback: load from file
        try:
            resource_demo = np.load("results/last_resource_trajectory.npy")
            st.success("✓ Loaded from results/last_resource_trajectory.npy")
        except Exception:
            st.warning("No training data — using demo trajectory")
            resource_demo = np.sin(4 * np.pi * np.arange(200) / 200) * 150 + 500

    # 3D surface chart
    t = np.arange(len(resource_demo))
    X, Y = np.meshgrid(t, np.linspace(0, 1000, 50))
    Z = np.tile(resource_demo, (50, 1))

    config = api_get("/config", {}) if api_online else {}
    target = config.get("prosperity_target", 500.0) if config else 500.0

    fig_3d = go.Figure()
    fig_3d.add_trace(go.Surface(z=Z, x=X, y=Y, colorscale="Viridis", name="Resource", opacity=0.9))
    fig_3d.add_trace(go.Surface(z=np.full_like(Z, target), x=X, y=Y, opacity=0.3, colorscale="Reds", name=f"Target ({target})"))
    fig_3d.add_trace(go.Scatter3d(
        x=t, y=np.zeros_like(t), z=resource_demo,
        mode="lines", line=dict(color="cyan", width=4), name="Trajectory",
    ))
    fig_3d.update_layout(
        title=f"3D Resource Trajectory — {len(resource_demo)} Steps",
        scene=dict(xaxis_title="Time", yaxis_title="Depth", zaxis_title="Resource"),
        height=650,
    )
    st.plotly_chart(fig_3d, use_container_width=True)


# ═══════════════════════════════════════════
#  TAB 5: INVENTORY (live)
# ═══════════════════════════════════════════

with tab_inventory:
    st.subheader("Resource Inventory — Live Status")

    inv_data = api_get("/inventory") if api_online else None

    if inv_data:
        source_tag = "LIVE" if inv_data.get("has_real_data") else "DEMO"
        st.caption(f"Data source: {source_tag}")

        icol1, icol2, icol3 = st.columns(3)
        with icol1:
            st.metric("Current Resource", f"{inv_data['current_resource']:.1f}", f"/ {inv_data['resource_budget']:.0f} budget")
        with icol2:
            st.metric("Prosperity Target", f"{inv_data['prosperity_target']:.1f}")
        with icol3:
            st.metric("Utilization", f"{inv_data['utilization_pct']}%")

        st.divider()
        pcol1, pcol2 = st.columns(2)
        with pcol1:
            st.metric("Peak Resource", f"{inv_data['peak_resource']:.1f}")
        with pcol2:
            st.metric("Low Resource", f"{inv_data['low_resource']:.1f}")

        # Gauge chart
        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=inv_data["current_resource"],
            delta={"reference": inv_data["prosperity_target"]},
            title={"text": "Resource Level vs Target"},
            gauge={
                "axis": {"range": [0, inv_data["resource_budget"]]},
                "bar": {"color": "#00e5ff"},
                "steps": [
                    {"range": [0, inv_data["prosperity_target"] * 0.5], "color": "rgba(231,76,60,0.2)"},
                    {"range": [inv_data["prosperity_target"] * 0.5, inv_data["prosperity_target"]], "color": "rgba(200,168,75,0.2)"},
                    {"range": [inv_data["prosperity_target"], inv_data["resource_budget"]], "color": "rgba(46,204,113,0.2)"},
                ],
                "threshold": {
                    "line": {"color": "gold", "width": 3},
                    "thickness": 0.8,
                    "value": inv_data["prosperity_target"],
                },
            },
        ))
        fig_gauge.update_layout(height=300)
        st.plotly_chart(fig_gauge, use_container_width=True)
    else:
        st.info("API offline — run `uvicorn api_server:app --port 8000` for live inventory data.")
        st.metric("Current Resource", "500.0", "Demo mode")
        st.metric("Prosperity Target", "500.0")


# ─── Footer ───
st.divider()
st.caption("Green Horizon Innovation · QM2ARL + ENGRAM-ENGN · GQ Live Brain · TELPAI-QUANTUM")
