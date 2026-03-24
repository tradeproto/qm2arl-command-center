# W&B Weave for Grok / topology traces (optional)

When you log Grok API calls and topology parsing, you can trace them with **W&B Weave** so prompts, responses, latency, and parse success appear as full traces in the dashboard.

## Setup

1. **Install Weave** (optional dependency):
   ```bash
   pip install weave
   ```

2. **Enable in config** (e.g. `configs/experiment1.yaml`):
   ```yaml
   use_weave_trace: true
   ```
   Use together with `use_wandb: true` and, if you want Grok calls traced, `use_grok_topology: true`.

## What gets traced

- **`_fetch_grok_topology_response`** (trainer): Grok API call — inputs (num_agents, config slice), output (response text), latency. Logged when Weave is initialized and Grok is called.
- **`parse_topology_response_to_graph`** (agents): Parser — input (response text, num_agents), output (graph), so you can see parse success (e.g. number of edges).
- **`suggest_coupling_topology`** (agents): Fallback topology — when the ring is used instead of Grok.

Weave is initialized after `wandb.init()` using the same project/entity (`entity/project`). If `weave` is not installed, the decorators are no-ops and nothing breaks.

## In the dashboard

- In your **Weave** project (or the linked W&B project), open **Traces** to see prompt–response pairs, parse outputs, and latency.
- Use this to debug Grok outputs, tune prompts, and check parse success rate.

## Example

```yaml
# configs/experiment1.yaml
use_wandb: true
use_grok_topology: true
use_weave_trace: true   # requires: pip install weave
# grok_api_key: "..." or set XAI_API_KEY
```
