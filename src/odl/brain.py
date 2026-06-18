"""
ODL Brain — knowledge map × value dimensions × coupling overlay.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .dimension_config import coupling_matrix, list_dimensions, signal_map
from .dimensions import Dimension

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_trinity_graph() -> Any:
    try:
        import networkx as nx
        from networkx.readwrite import json_graph
        from trinity_nexus.search import get_subgraph

        graph_path = _REPO_ROOT / "trinity_nexus" / "trinity_graph.json"
        if not graph_path.is_file():
            return None, {"error": "trinity_graph.json not found — run python -m trinity_nexus"}

        data = __import__("json").loads(graph_path.read_text(encoding="utf-8"))
        edge_key = "links" if "links" in data else "edges"
        G = json_graph.node_link_graph(data, edges=edge_key)
        return G, None
    except Exception as e:
        return None, {"error": f"{type(e).__name__}: {e}"}


def tag_node_for_dimensions(node: dict[str, Any], smap: dict[str, dict[str, Any]]) -> list[str]:
    """Return dimension ids that this Trinity node feeds."""
    path = (node.get("path") or node.get("node_id") or node.get("id") or "").lower()
    name = (node.get("name") or "").lower()
    project = (node.get("project") or "").lower()
    tags = [t.lower() for t in (node.get("tags") or [])]
    meta = node.get("meta") or {}
    summary = (meta.get("summary") or "").lower() if isinstance(meta, dict) else ""
    haystack = " ".join([path, name, project, summary, " ".join(tags)])

    matched: list[str] = []
    for dim_id, rules in smap.items():
        score = 0
        for pat in rules.get("path_patterns") or []:
            if pat.lower() in haystack:
                score += 2
        for proj in rules.get("projects") or []:
            if proj.lower() == project or proj.lower() in tags:
                score += 3
        for rf in rules.get("result_files") or []:
            if rf.lower() in path or Path(rf).name.lower() in haystack:
                score += 4
        if score > 0:
            matched.append((score, dim_id))
    matched.sort(reverse=True)
    return [d for _, d in matched[:3]]


def coverage_honesty(resonance: dict[str, Any] | None) -> dict[str, Any]:
    """Banner payload: provisional vs measured resonance."""
    if not resonance:
        return {"level": "unknown", "message": "No resonance state."}
    cov = resonance.get("coverage") or {}
    pct = float(cov.get("coverage_pct", 0))
    missing = cov.get("missing") or []
    verdict = resonance.get("verdict", "")
    if pct < 80:
        return {
            "level": "warning",
            "provisional": True,
            "coverage_pct": pct,
            "measured": cov.get("measured") or [],
            "missing": missing,
            "message": (
                f"Coverage {pct:.0f}% — verdict **{verdict}** is provisional. "
                f"Dimensions defaulted to target: {', '.join(missing) or 'none'}."
            ),
        }
    return {
        "level": "ok",
        "provisional": False,
        "coverage_pct": pct,
        "measured": cov.get("measured") or [],
        "missing": missing,
        "message": f"Coverage {pct:.0f}% — {len(cov.get('measured') or [])} dimensions measured live.",
    }


def build_brain_graph(
    *,
    project: str | None = None,
    limit: int = 120,
    search: str | None = None,
) -> dict[str, Any]:
    G, err = _load_trinity_graph()
    if err:
        return err

    smap = signal_map()
    dims_meta = {d["id"]: d for d in list_dimensions()}

    if project:
        try:
            from trinity_nexus.search import get_subgraph
            sub = get_subgraph(project, G)
            nodes_in = {n["id"]: n for n in sub.get("nodes", [])}
            edges_in = sub.get("links", [])
        except Exception:
            nodes_in = {nid: dict(attrs, id=nid) for nid, attrs in G.nodes(data=True)}
            edges_in = []
    else:
        nodes_in = {nid: dict(attrs, id=nid) for nid, attrs in G.nodes(data=True)}
        edges_in = []

    if search:
        q = search.lower()
        nodes_in = {
            nid: n for nid, n in nodes_in.items()
            if q in nid.lower() or q in (n.get("name") or "").lower() or q in (n.get("project") or "").lower()
        }

    # Prioritize nodes that match dimensions, then by degree
    scored = []
    for nid, n in nodes_in.items():
        dim_tags = tag_node_for_dimensions(n, smap)
        scored.append((len(dim_tags), G.degree(nid) if nid in G else 0, nid, n, dim_tags))
    scored.sort(reverse=True)
    picked = scored[: max(10, min(limit, 300))]

    nodes_out = []
    id_set = set()
    for _, _, nid, n, dim_tags in picked:
        id_set.add(nid)
        primary = dim_tags[0] if dim_tags else None
        nodes_out.append({
            "id": nid,
            "name": n.get("name", nid),
            "project": n.get("project"),
            "path": n.get("path"),
            "dimensions": dim_tags,
            "primary_dimension": primary,
            "primary_label": dims_meta.get(primary, {}).get("label") if primary else None,
        })

    links_out = []
    if not edges_in:
        for u, v in G.edges():
            if u in id_set and v in id_set:
                links_out.append({"source": u, "target": v})
    else:
        for e in edges_in:
            src, tgt = e.get("source"), e.get("target")
            if src in id_set and tgt in id_set:
                links_out.append({"source": src, "target": tgt})

    dim_counts: dict[str, int] = {d.value: 0 for d in Dimension}
    for node in nodes_out:
        for d in node.get("dimensions") or []:
            if d in dim_counts:
                dim_counts[d] += 1

    return {
        "nodes": nodes_out,
        "links": links_out[:2000],
        "dimension_counts": dim_counts,
        "total_available": len(nodes_in),
        "shown": len(nodes_out),
        "project_filter": project,
    }


def brain_state(resonance: dict[str, Any] | None = None) -> dict[str, Any]:
    ids, matrix = coupling_matrix()
    return {
        "dimensions": list_dimensions(),
        "coupling": {"ids": ids, "matrix": matrix},
        "coverage": coverage_honesty(resonance),
        "signal_map": signal_map(),
    }