# QM2ARL

Project for QM2ARL code and simulations.

## Structure

- **`src/`** — Source code and core modules
- **`simulations/`** — Simulation scripts and runs
- **`configs/`** — Configuration files for experiments
- **`data/`** — Input data (optional)
- **`results/`** — Simulation outputs and figures
- **`notebooks/`** — Jupyter notebooks for analysis
- **`tests/`** — Unit and integration tests

## Quick Start

1. `pip install -r requirements.txt`
2. `python simulations/basic_qm2arl_scale.py` — runs TELPAIEnv + multi-agent training; plot is written to `results/rewards_n{num_agents}.png`.

## Setup

```bash
cd QM2ARL
python3 -m venv .venv
source .venv/bin/activate   # Linux/macOS; on Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Running simulations

From the project root (with venv activated):

```bash
python simulations/basic_qm2arl_scale.py
```

Uses `configs/default.yaml`; plot is written to `results/rewards_n{num_agents}.png`.
