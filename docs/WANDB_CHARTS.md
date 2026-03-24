# W&B Custom Charts (episode_summary_table)

The trainer logs **`episode_summary_table`** with columns: `episode`, `reward_mean`, `resource_final`, `explore_pct`, `extract_pct`, `invest_pct`.

## Using it in the dashboard

1. Open your run → **+ Add panel** → **Custom chart**.
2. Select **`episode_summary_table`** as the data source.
3. Use the Vega-Lite editor (or presets) to define the chart.

## Advanced tips

- **Multi-faceted views:** Combine line + bar in one panel (e.g. resource line + stacked action bar). Use layered or concatenated specs in Vega-Lite.
- **Interactive tooltips:** Enable tooltips in the chart config so hovering shows episode details (reward_mean, resource_final, action %s).
- **Vega-Lite examples:** [https://vega.github.io/vega-lite/examples/](https://vega.github.io/vega-lite/examples/) — copy-paste JSON specs into the W&B editor and map fields to your table columns (`episode`, `resource_final`, `explore_pct`, etc.).

## Example ideas

- **Line:** `resource_final` vs `episode` with a rule at y = 500 (prosperity target).
- **Stacked bar:** `explore_pct`, `extract_pct`, `invest_pct` per episode.
- **Scatter:** `reward_mean` vs `resource_final` or vs deviation from 500.
- **Combo:** Resource line + action stack bar in one panel; save as preset for reuse across runs.
