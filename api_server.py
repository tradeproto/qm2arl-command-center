"""
GQ (Grok Quantum) Live Brain — FastAPI Backend
Serves QM2ARL training data, agent states, and GQ query endpoint.
Run: uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload
"""
from __future__ import annotations

import os
import json
import urllib.request
from pathlib import Path
from typing import Any

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="GQ Live Brain — QM2ARL API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

RESULTS_DIR = Path("results")
CONFIGS_DIR = Path("configs")

# xAI Grok API
XAI_CHAT_URL = "https://api.x.ai/v1/chat/completions"
GROK_MODEL = os.environ.get("GROK_MODEL", "grok-2")
XAI_API_KEY = os.environ.get("XAI_API_KEY", "")


# ─── Models ───

class GQQuery(BaseModel):
    question: str
    context: str = "qm2arl_geophysical"

class GQResponse(BaseModel):
    answer: str
    model: str
    context: str


# ─── Helper: Load latest training data ───

def load_resource_trajectory() -> list[float]:
    path = RESULTS_DIR / "last_resource_trajectory.npy"
    if path.exists():
        data = np.load(str(path))
        return data.tolist()
    return []

def load_training_config() -> dict:
    path = CONFIGS_DIR / "default.yaml"
    if path.exists():
        import yaml
        with open(path) as f:
            return yaml.safe_load(f)
    return {}

def get_latest_wandb_metrics() -> dict:
    """Scan wandb dir for latest run summary."""
    wandb_dir = Path("wandb")
    if not wandb_dir.exists():
        return {}
    runs = sorted(wandb_dir.glob("run-*"), key=lambda p: p.stat().st_mtime, reverse=True)
    for run_dir in runs[:1]:
        summary_file = run_dir / "files" / "wandb-summary.json"
        if summary_file.exists():
            with open(summary_file) as f:
                return json.load(f)
    return {}


# ─── Routes ───

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "GQ Live Brain — QM2ARL API",
        "grok_configured": bool(XAI_API_KEY),
        "has_training_data": (RESULTS_DIR / "last_resource_trajectory.npy").exists(),
    }


@app.get("/trajectory")
def get_trajectory():
    """Return the latest resource trajectory from training."""
    data = load_resource_trajectory()
    if not data:
        raise HTTPException(404, "No training trajectory found. Run training first.")
    return {
        "steps": len(data),
        "trajectory": data,
        "min": min(data),
        "max": max(data),
        "mean": sum(data) / len(data),
    }


@app.get("/agent-scores")
def get_agent_scores():
    """Return agent performance metrics from latest wandb run."""
    metrics = get_latest_wandb_metrics()
    if not metrics:
        # Generate demo scores
        return {
            "source": "demo",
            "agents": [
                {"id": i, "mean_reward": round(np.random.uniform(0.3, 0.9), 3),
                 "hmu": round(np.random.uniform(0.7, 0.95), 3),
                 "extracts": int(np.random.randint(10, 50)),
                 "invests": int(np.random.randint(20, 60)),
                 "explores": int(np.random.randint(15, 40))}
                for i in range(4)
            ],
        }
    return {
        "source": "wandb",
        "metrics": {k: v for k, v in metrics.items() if not k.startswith("_")},
    }


@app.get("/inventory")
def get_inventory():
    """Return current resource inventory state."""
    traj = load_resource_trajectory()
    if traj:
        current = traj[-1]
        peak = max(traj)
        low = min(traj)
    else:
        current, peak, low = 500.0, 750.0, 250.0

    config = load_training_config()
    target = config.get("prosperity_target", 500.0) if config else 500.0
    budget = config.get("resource_budget", 1000.0) if config else 1000.0

    return {
        "current_resource": round(current, 2),
        "peak_resource": round(peak, 2),
        "low_resource": round(low, 2),
        "prosperity_target": target,
        "resource_budget": budget,
        "utilization_pct": round((current / budget) * 100, 1) if budget else 0,
        "has_real_data": bool(traj),
    }


@app.get("/config")
def get_config():
    """Return the current training configuration."""
    return load_training_config()


@app.post("/gq/query", response_model=GQResponse)
def gq_query(req: GQQuery):
    """
    Ask GQ (Grok Quantum) a question.
    Routes to xAI Grok API with QM2ARL context.
    Falls back to local response if no API key.
    """
    if not XAI_API_KEY:
        return GQResponse(
            answer=f"GQ is in offline mode (no XAI_API_KEY configured). Your question: '{req.question}' — "
                   f"To enable live GQ responses, set the XAI_API_KEY environment variable with your xAI API key.",
            model="offline",
            context=req.context,
        )

    # Build context from latest training data
    traj = load_resource_trajectory()
    metrics = get_latest_wandb_metrics()
    config = load_training_config()

    system_prompt = (
        "You are GQ (Grok Quantum), the live AI brain of the QM2ARL (Quantum Multi-Agent Reinforcement Learning) "
        "system built by Green Horizon Innovation. You operate within the TELPAI-QUANTUM geophysical exploration "
        "platform and the ENGRAM-ENGN adaptive reasoning layer. "
        "You have access to real-time training metrics, resource trajectories, and agent performance data. "
        "Respond concisely and technically. You are speaking to the PI (Principal Investigator).\n\n"
        f"Current training config: {json.dumps(config, default=str)[:500] if config else 'No config loaded'}\n"
        f"Latest trajectory: {len(traj)} steps, "
        f"current resource: {traj[-1]:.1f}" if traj else "No trajectory data" + "\n"
        f"Latest wandb metrics: {json.dumps({k:v for k,v in metrics.items() if not k.startswith('_')}, default=str)[:500] if metrics else 'No metrics'}"
    )

    payload = json.dumps({
        "model": GROK_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": req.question},
        ],
        "temperature": 0.3,
        "max_tokens": 1000,
    }).encode()

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {XAI_API_KEY}",
    }

    try:
        request = urllib.request.Request(XAI_CHAT_URL, data=payload, headers=headers)
        with urllib.request.urlopen(request, timeout=30) as resp:
            body = json.loads(resp.read().decode())
            answer = body["choices"][0]["message"]["content"]
            return GQResponse(answer=answer, model=GROK_MODEL, context=req.context)
    except Exception as e:
        return GQResponse(
            answer=f"GQ encountered an error: {str(e)}",
            model="error",
            context=req.context,
        )


# ─── Startup message ───

@app.on_event("startup")
def startup():
    print("\n╔══════════════════════════════════════════════════╗")
    print("║  GQ LIVE BRAIN — QM2ARL FastAPI Server          ║")
    print(f"║  Grok: {'✓ API KEY SET' if XAI_API_KEY else '✗ OFFLINE MODE':38s}║")
    print(f"║  Training data: {'✓ FOUND' if (RESULTS_DIR / 'last_resource_trajectory.npy').exists() else '✗ NOT FOUND':30s}║")
    print("╠══════════════════════════════════════════════════╣")
    print("║  GET  /health          — Server status           ║")
    print("║  GET  /trajectory      — Resource trajectory     ║")
    print("║  GET  /agent-scores    — Agent performance       ║")
    print("║  GET  /inventory       — Resource inventory      ║")
    print("║  GET  /config          — Training config         ║")
    print("║  POST /gq/query        — Ask GQ (Grok Quantum)  ║")
    print("╚══════════════════════════════════════════════════╝\n")
