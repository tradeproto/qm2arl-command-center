"""ODL Brain tab — plot helpers and coverage banner."""
from __future__ import annotations

import math
from typing import Any

import plotly.graph_objects as go
import streamlit as st

DIM_COLORS = {
    "prosperity": "#2ecc71",
    "planet": "#27ae60",
    "equity": "#3498db",
    "health": "#e74c3c",
    "knowledge": "#9b59b6",
    "connection": "#f39c12",
}


def render_coverage_banner(coverage: dict[str, Any] | None) -> None:
    if not coverage:
        return
    level = coverage.get("level", "unknown")
    msg = coverage.get("message", "")
    if level == "warning" or coverage.get("provisional"):
        st.warning(msg)
    elif level == "ok":
        st.success(msg)
    else:
        st.info(msg)


def plot_coupling_heatmap(coupling: dict[str, Any]) -> None:
    ids = coupling.get("ids") or []
    matrix = coupling.get("matrix") or []
    if not ids or not matrix:
        st.info("No coupling matrix configured.")
        return
    fig = go.Figure(data=go.Heatmap(
        z=matrix,
        x=[i.title() for i in ids],
        y=[i.title() for i in ids],
        colorscale="RdBu",
        zmid=0,
        text=[[f"{v:+.2f}" for v in row] for row in matrix],
        texttemplate="%{text}",
        hoverongaps=False,
    ))
    fig.update_layout(
        height=420,
        margin=dict(l=60, r=20, t=30, b=60),
        paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig, use_container_width=True)


def plot_brain_graph(graph: dict[str, Any]) -> None:
    nodes = graph.get("nodes") or []
    links = graph.get("links") or []
    if not nodes:
        st.info("No graph nodes. Run `python -m trinity_nexus` to build the knowledge map.")
        return

    project_nodes: dict[str, list[int]] = {}
    for i, node in enumerate(nodes):
        proj = node.get("primary_dimension") or node.get("project") or "other"
        project_nodes.setdefault(proj, []).append(i)

    n_groups = max(len(project_nodes), 1)
    pos_x = [0.0] * len(nodes)
    pos_y = [0.0] * len(nodes)
    for gi, (grp, indices) in enumerate(project_nodes.items()):
        cx = math.cos(2 * math.pi * gi / n_groups) * 3
        cy = math.sin(2 * math.pi * gi / n_groups) * 3
        for k, idx in enumerate(indices):
            angle = 2 * math.pi * k / max(len(indices), 1)
            r = 0.35 + 0.04 * math.sqrt(k)
            pos_x[idx] = cx + r * math.cos(angle)
            pos_y[idx] = cy + r * math.sin(angle)

    id_to_idx = {nodes[i].get("id", str(i)): i for i in range(len(nodes))}
    edge_x, edge_y = [], []
    for link in links[:1500]:
        src, tgt = link.get("source"), link.get("target")
        if src in id_to_idx and tgt in id_to_idx:
            si, ti = id_to_idx[src], id_to_idx[tgt]
            edge_x.extend([pos_x[si], pos_x[ti], None])
            edge_y.extend([pos_y[si], pos_y[ti], None])

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=edge_x, y=edge_y, mode="lines",
        line=dict(width=0.4, color="rgba(150,150,200,0.2)"),
        hoverinfo="none",
    ))

    for dim_id, color in DIM_COLORS.items():
        xs, ys, texts, hovers = [], [], [], []
        for i, node in enumerate(nodes):
            pd = node.get("primary_dimension")
            if pd == dim_id or (not pd and dim_id == "other"):
                xs.append(pos_x[i])
                ys.append(pos_y[i])
                texts.append((node.get("name") or "")[:24])
                hovers.append(
                    f"<b>{node.get('name')}</b><br>"
                    f"dims: {', '.join(node.get('dimensions') or [])}<br>"
                    f"{node.get('path', '')[:80]}"
                )
        if xs:
            fig.add_trace(go.Scatter(
                x=xs, y=ys, mode="markers+text",
                text=texts,
                textposition="top center",
                textfont=dict(size=8),
                marker=dict(size=9, color=color, line=dict(width=0.5, color="#fff")),
                name=dim_id.title(),
                hovertext=hovers,
                hoverinfo="text",
            ))

    # nodes without primary dimension
    other_x, other_y, other_t = [], [], []
    for i, node in enumerate(nodes):
        if not node.get("primary_dimension"):
            other_x.append(pos_x[i])
            other_y.append(pos_y[i])
            other_t.append((node.get("name") or "")[:20])
    if other_x:
        fig.add_trace(go.Scatter(
            x=other_x, y=other_y, mode="markers",
            marker=dict(size=6, color="#636e72"),
            name="Untagged",
            hoverinfo="skip",
        ))

    fig.update_layout(
        showlegend=True,
        height=520,
        margin=dict(l=10, r=10, t=30, b=10),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        f"Showing **{graph.get('shown', 0)}** of **{graph.get('total_available', 0)}** nodes "
        f"(dimension-tagged priority). Edge color = knowledge links."
    )