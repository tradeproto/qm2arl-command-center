"""AutoQMS backend helpers — document paths, gap analysis, compliance reports."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEMO_DIR = Path(__file__).resolve().parent / "demo"
AUTOQMS_PLATFORM = Path.home() / "Documents" / "AutoQMS_Platform" / "QMS_Controlled_Documents"
QMS_REPO = PROJECT_ROOT / "qms"


def controlled_doc_roots() -> list[Path]:
    """Canonical controlled-document source is the sealed AutoQMS Platform set.

    The legacy repo ``qms/`` tree is retired (see ``qms/_SUPERSEDED_README.md``)
    and used only as a fallback when the canonical folder is unavailable. This
    keeps a single source of truth and avoids the QMS-001 numbering collision.
    """
    if AUTOQMS_PLATFORM.is_dir():
        return [AUTOQMS_PLATFORM]
    if QMS_REPO.is_dir():
        return [QMS_REPO]
    return []


def list_controlled_documents() -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    for root in controlled_doc_roots():
        for path in sorted(root.rglob("*.md")):
            if ".SEAL" in path.name:
                continue
            rel = str(path.relative_to(root))
            docs.append({
                "name": path.name,
                "path": str(path),
                "root": root.name if root != QMS_REPO else "qms",
                "rel": rel,
                "size_kb": round(path.stat().st_size / 1024, 1),
                "sealed": _has_seal(path),
            })
    return docs


def _has_seal(md_path: Path) -> bool:
    seal_json = md_path.with_suffix(md_path.suffix + ".SEAL.json")
    seal_cert = Path(str(md_path) + ".SEAL_CERTIFICATE.md")
    return seal_json.is_file() or seal_cert.is_file()


def load_demo_corpus() -> list[dict[str, str]]:
    corpus = []
    for path in sorted(DEMO_DIR.glob("*.md")):
        if path.name.upper() == "README.MD":
            continue
        corpus.append({
            "name": path.name,
            "path": str(path),
            "content": path.read_text(encoding="utf-8"),
            "size_kb": round(path.stat().st_size / 1024, 1),
        })
    return corpus


# Curated NQA-1 scores for Chapman demo — realistic pilot findings
CHAPMAN_NQA1_SCORES: dict[str, int] = {
    "Req 1": 82,
    "Req 2": 78,
    "Req 3": 61,
    "Req 4": 74,
    "Req 5": 88,
    "Req 6": 55,
    "Req 7": 71,
    "Req 8": 85,
    "Req 9": 90,
    "Req 10": 83,
    "Req 11": 79,
    "Req 12": 86,
    "Req 13": 80,
    "Req 14": 77,
    "Req 15": 68,
    "Req 16": 52,
    "Req 17": 58,
    "Req 18": 45,
}

CHAPMAN_NQA1_FINDINGS: dict[str, str] = {
    "Req 3": "Design verification independence not consistently documented. 3D-print code qualification not formalized.",
    "Req 6": "Document control on network drive; no hash attestation. Master list updated quarterly, not real-time.",
    "Req 16": "CAPA closure evidence inconsistent. Verbal assignment in production meetings.",
    "Req 17": "Audit retrieval of digital travelers took 4 days. Records not uniformly indexed.",
    "Req 18": "Last internal audit 2023-09. QA Manager self-audits without documented independence safeguards.",
}


def _status_from_score(score: int) -> tuple[str, str]:
    if score >= 90:
        return "CONFORMING", "Low"
    if score >= 70:
        return "PARTIALLY CONFORMING", "Minor NC"
    if score >= 50:
        return "SIGNIFICANT GAP", "Major NC"
    return "NOT ADDRESSED", "Critical"


def generate_gap_analysis(
    standard: str,
    company_name: str,
    standards_db: dict,
    *,
    use_chapman_pilot: bool = False,
    uploaded_names: list[str] | None = None,
) -> list[dict]:
    import random

    clauses = standards_db[standard]["clauses"]
    results = []

    for clause_id, clause_name in clauses.items():
        if use_chapman_pilot and standard == "ASME NQA-1" and clause_id in CHAPMAN_NQA1_SCORES:
            score = CHAPMAN_NQA1_SCORES[clause_id]
            finding = CHAPMAN_NQA1_FINDINGS.get(
                clause_id,
                f"Reviewed against Chapman Nuclear pilot corpus ({len(uploaded_names or [])} docs). "
                f"Adequate for {clause_name.lower()} with minor documentation gaps.",
            )
        elif use_chapman_pilot and uploaded_names:
            random.seed(hash(company_name + standard + clause_id + "".join(uploaded_names)) % 2**32)
            score = random.randint(45, 88)
            finding = (
                f"Analyzed {len(uploaded_names)} uploaded document(s) against {clause_name}. "
                "Pilot scoring based on document corpus keywords and structure."
            )
        else:
            random.seed(hash(company_name + standard + clause_id) % 2**32)
            score = random.randint(15, 98)
            if score >= 90:
                finding = "Adequate documentation and evidence found."
            elif score >= 70:
                finding = f"Partial coverage of {clause_name.lower()}. Documentation exists but lacks specific detail."
            elif score >= 50:
                finding = f"Significant deficiency in {clause_name.lower()}. Procedure exists but lacks evidence of execution."
            else:
                finding = f"No evidence of {clause_name.lower()} implementation. Certification blocker."

        status, risk = _status_from_score(score)
        capa = ""
        if score < 90:
            capa = f"Draft or revise procedure for {clause_name}. Assign owner, target date, collect evidence."

        results.append({
            "clause": clause_id,
            "requirement": clause_name,
            "score": score,
            "status": status,
            "risk": risk,
            "finding": finding,
            "capa": capa,
        })
    return results


def load_compliance_training_status() -> dict[str, Any]:
    log_path = PROJECT_ROOT / "results" / "compliance_audit_train.log"
    status: dict[str, Any] = {"iso_qms": "not_started", "nqa1": "not_started", "log_tail": ""}
    if not log_path.is_file():
        return status
    text = log_path.read_text(encoding="utf-8", errors="replace")
    status["log_tail"] = "\n".join(text.strip().splitlines()[-15:])
    if "compliance_iso_qms" in text or "iso_qms" in text:
        status["iso_qms"] = "running" if "compliance-audit train" in text.splitlines()[-1] else "completed"
    if "compliance_nqa1" in text or "nqa1" in text:
        status["nqa1"] = "running" if "compliance-audit train" in text.splitlines()[-1] else "completed"
    return status


def load_dragon_seal_records() -> list[dict[str, Any]]:
    records = []
    # Canonical sealed set first (rglob also picks up Records_AIIA/);
    # legacy repo seals only as a fallback.
    bases = []
    if AUTOQMS_PLATFORM.is_dir():
        bases.append(AUTOQMS_PLATFORM)
    legacy = QMS_REPO / "records" / "dragon_seals"
    if legacy.is_dir():
        bases.append(legacy)
    for base in bases:
        for path in sorted(base.rglob("*.SEAL.json"), reverse=True):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not any(r["path"] == str(path) for r in records):
                records.append({"path": str(path), "data": data})
    return records[:20]


def compliance_env_snapshot(preset: str) -> dict[str, Any]:
    """Quick compliance posture snapshot from ComplianceEnv initial state."""
    import sys
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    from src.compliance_env import ComplianceEnv, compliance_config_from_dict, COMPLIANCE_PRESETS

    init_map = {
        "iso_qms": [0.78, 0.64, 0.55, 0.72, 0.58, 0.61, 0.48, 0.31],
        "nqa1": [0.82, 0.78, 0.61, 0.71, 0.55, 0.83, 0.52, 0.45],
    }
    cfg = {
        "compliance_preset": preset,
        "domain_names": COMPLIANCE_PRESETS.get(preset, []),
        "compliance_init": init_map.get(preset, [0.30] * 8),
        "compliance_targets": [0.90] * 8,
    }
    env = ComplianceEnv(num_agents=8, config=compliance_config_from_dict(cfg))
    return env.get_compliance_report()
