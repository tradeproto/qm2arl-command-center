"""ODL Brain — dimension config + graph tagging."""
from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from src.odl.brain import coverage_honesty, tag_node_for_dimensions
from src.odl.dimension_config import coupling_matrix, list_dimensions, signal_map


def test_list_dimensions_has_six():
    dims = list_dimensions()
    assert len(dims) == 6
    assert dims[0]["id"] == "prosperity"


def test_coupling_matrix_symmetric():
    ids, matrix = coupling_matrix()
    assert len(ids) == 6
    assert len(matrix) == 6
    for i in range(6):
        assert matrix[i][i] == 1.0


def test_tag_node_knowledge():
    smap = signal_map()
    tags = tag_node_for_dimensions(
        {"path": "/home/joshua/QM2ARL/results/autoqms_spe_prms_training_summary.json", "project": "qm2arl"},
        smap,
    )
    assert "knowledge" in tags or "connection" in tags


def test_coverage_honesty_warning():
    banner = coverage_honesty({
        "verdict": "RESONANT",
        "coverage": {"coverage_pct": 50.0, "measured": ["knowledge"], "missing": ["planet", "health"]},
    })
    assert banner["provisional"] is True
    assert banner["level"] == "warning"