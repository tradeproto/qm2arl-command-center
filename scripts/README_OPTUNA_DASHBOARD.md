# Optuna Dashboard — "This site can't be reached" / ERR_CONNECTION_REFUSED

**That error means nothing is listening on port 8080 yet.** The dashboard is a separate process you must start and leave running.

## Do this (in order)

### 1. Create a study first (so the DB exists)
From repo root, with venv active:
```bash
source .venv/bin/activate
python3 scripts/tune.py --n-trials 1
```
(One trial is enough to create `telpai_study.db`.)

### 2. Start the dashboard (leave this terminal open)
In a **new** terminal, from repo root:
```bash
cd ~/QM2ARL
source .venv/bin/activate
optuna-dashboard sqlite:///telpai_study.db
```
You should see something like:
```
Listening on http://127.0.0.1:8080/
```
**Do not close this terminal.** The server runs here.

### 3. Open the URL in your browser
Only now open: **http://localhost:8080** (or http://127.0.0.1:8080).

---

## If you're on WSL or a remote machine
- Start the dashboard with:
  ```bash
  optuna-dashboard sqlite:///telpai_study.db --host 0.0.0.0 --port 8080
  ```
- Then either open http://localhost:8080 on that machine, or from your laptop use SSH port forwarding:
  ```bash
  ssh -L 8080:localhost:8080 user@remote
  ```
  and open http://localhost:8080 on your laptop.

## Quick one-liner (after at least one trial exists)
```bash
cd ~/QM2ARL && source .venv/bin/activate && optuna-dashboard sqlite:///telpai_study.db && echo "Open http://localhost:8080"
```
