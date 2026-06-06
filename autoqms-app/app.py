"""
AutoQMS Web Application — Chapman Nuclear x Green Horizon Innovation
Industrial-grade AI Quality & Compliance Platform

Run:  streamlit run autoqms-app/app.py --server.port 8502
"""
from __future__ import annotations

import datetime
import json
import os
import sys
import time
from pathlib import Path

import streamlit as st

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import hashlib

from services import (
    AUTOQMS_PLATFORM,
    compliance_env_snapshot,
    generate_gap_analysis,
    list_controlled_documents,
    load_compliance_training_status,
    load_demo_corpus,
    load_dragon_seal_records,
)

MASTER_API = os.getenv("MASTER_CONSOLE_URL", "http://localhost:8001")
DRAGON_SEAL_NFT_PATH = os.path.join(os.path.expanduser("~"), "dragon_seal_nft")

st.set_page_config(
    page_title="AutoQMS — AI Quality & Compliance",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

STANDARDS_DB = {
    "ISO 9001:2015": {
        "clauses": {
            "4.1": "Understanding the organization and its context",
            "4.2": "Understanding the needs and expectations of interested parties",
            "4.3": "Determining the scope of the QMS",
            "4.4": "Quality management system and its processes",
            "5.1": "Leadership and commitment",
            "5.2": "Quality policy",
            "5.3": "Organizational roles, responsibilities, and authorities",
            "6.1": "Actions to address risks and opportunities",
            "6.2": "Quality objectives and planning to achieve them",
            "6.3": "Planning of changes",
            "7.1": "Resources",
            "7.2": "Competence",
            "7.3": "Awareness",
            "7.4": "Communication",
            "7.5": "Documented information",
            "8.1": "Operational planning and control",
            "8.2": "Requirements for products and services",
            "8.3": "Design and development",
            "8.4": "Control of externally provided processes",
            "8.5": "Production and service provision",
            "8.6": "Release of products and services",
            "8.7": "Control of nonconforming outputs",
            "9.1": "Monitoring, measurement, analysis, and evaluation",
            "9.2": "Internal audit",
            "9.3": "Management review",
            "10.1": "General (Improvement)",
            "10.2": "Nonconformity and corrective action",
            "10.3": "Continual improvement",
        },
        "color": "#2196F3",
    },
    "ISO/IEC 42001:2023": {
        "clauses": {
            "4.1": "Understanding the organization (AI context)",
            "4.2": "Interested parties (AI stakeholders)",
            "4.3": "Scope of the AIMS",
            "5.1": "Leadership commitment (AI governance)",
            "5.2": "AI policy",
            "6.1": "AI risk assessment",
            "6.2": "AI objectives",
            "7.1": "Resources for AI systems",
            "7.2": "AI competence",
            "7.5": "Documented information (AI records)",
            "8.1": "Operational planning (AI lifecycle)",
            "8.2": "AI risk treatment",
            "8.3": "AI system impact assessment",
            "8.4": "AI system lifecycle processes",
            "9.1": "Monitoring AI performance",
            "9.2": "Internal audit (AIMS)",
            "9.3": "Management review (AIMS)",
            "10.1": "Nonconformity and corrective action (AI)",
            "10.2": "Continual improvement (AI)",
        },
        "color": "#9C27B0",
    },
    "ASME NQA-1": {
        "clauses": {
            "Req 1": "Organization",
            "Req 2": "Quality Assurance Program",
            "Req 3": "Design Control",
            "Req 4": "Procurement Document Control",
            "Req 5": "Instructions, Procedures, and Drawings",
            "Req 6": "Document Control",
            "Req 7": "Control of Purchased Items and Services",
            "Req 8": "Identification and Control of Items",
            "Req 9": "Control of Special Processes",
            "Req 10": "Inspection",
            "Req 11": "Test Control",
            "Req 12": "Control of Measuring and Test Equipment",
            "Req 13": "Handling, Storage, and Shipping",
            "Req 14": "Inspection, Test, and Operating Status",
            "Req 15": "Nonconforming Items",
            "Req 16": "Corrective Action",
            "Req 17": "Quality Assurance Records",
            "Req 18": "Audits",
        },
        "color": "#FF9800",
    },
    "ISO 27001:2022": {
        "clauses": {
            "4.1": "Understanding the organization (ISMS context)",
            "5.1": "Leadership and commitment (ISMS)",
            "6.1": "Information security risk assessment",
            "6.2": "Information security objectives",
            "7.5": "Documented information (ISMS)",
            "8.1": "Operational planning and control (ISMS)",
            "8.2": "Information security risk treatment",
            "9.1": "Monitoring and measurement (ISMS)",
            "9.2": "Internal audit (ISMS)",
            "9.3": "Management review (ISMS)",
            "10.1": "Nonconformity and corrective action (ISMS)",
            "A.5": "Organizational controls",
            "A.6": "People controls",
            "A.7": "Physical controls",
            "A.8": "Technological controls",
        },
        "color": "#F44336",
    },
}


def render_sidebar():
    st.sidebar.image(
        "https://img.shields.io/badge/AutoQMS-v1.0-blue?style=for-the-badge",
        use_container_width=True,
    )
    st.sidebar.title("AutoQMS")
    st.sidebar.caption(
        "Industrial-Grade AI Quality & Compliance Platform\n\n"
        "Green Horizon Innovation (SDVOSB)\n"
        "x Chapman Nuclear"
    )
    st.sidebar.divider()

    page = st.sidebar.radio("Navigation", [
        "Chapman Test Drive",
        "Dashboard",
        "Dragon Seal Signing",
        "Gap Analysis",
        "Compliance Training",
        "CAPA Management",
        "Audit Preparation",
        "Document Library",
        "Settings",
    ])
    st.sidebar.divider()
    st.sidebar.caption(
        "**Standards Supported:**\n"
        "- ISO 9001:2015\n"
        "- ISO/IEC 42001:2023\n"
        "- ASME NQA-1\n"
        "- ISO 27001:2022\n"
        "- CMMC Level 2"
    )
    return page


def render_test_drive():
    st.title("Chapman Test Drive")
    st.caption("Guided walkthrough — AutoQMS NQA-1 Agent pilot for Chapman Nuclear")

    st.success(
        "**Welcome, Eric.** This sandbox lets you run Chapman Nuclear QA documents through AutoQMS "
        "without uploading real client data. Use the demo corpus first, then try your own files when ready."
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Demo Documents", "4", "QA manual, design control, supplier qual, CAPA log")
    with col2:
        st.metric("Primary Standard", "ASME NQA-1", "Division 11 agents")
    with col3:
        st.metric("GHI Day Zero", "2026-06-05", "QMS-003 signed")

    st.divider()
    st.subheader("5-Minute Test Drive")

    steps = [
        ("1", "Gap Analysis", "Run the **Chapman Nuclear NQA-1 Pilot** on the demo corpus. Review Req 3, 6, 16, 17, 18 findings."),
        ("2", "CAPA Management", "Open pre-loaded CAPAs. Create a CAR from a gap finding (e.g., 3D print code qualification)."),
        ("3", "Document Library", "Browse GHI's controlled QMS/NQA-1 document set — 30+ Dragon Seal attested procedures."),
        ("4", "Dragon Seal", "Verify QMS-003 policy attestation. Sign a pilot document offline."),
        ("5", "Compliance Training", "Launch Division 11 NQA-1 agent training (optional — requires Master Console API)."),
    ]
    for num, title, desc in steps:
        st.markdown(f"**Step {num} — {title}**  \n{desc}")

    st.divider()
    st.subheader("Quick Start — Chapman NQA-1 Pilot")

    if st.button("Run Chapman NQA-1 Gap Analysis Now", type="primary"):
        corpus = load_demo_corpus()
        results = generate_gap_analysis(
            "ASME NQA-1",
            "Chapman Nuclear LLC",
            STANDARDS_DB,
            use_chapman_pilot=True,
            uploaded_names=[d["name"] for d in corpus],
        )
        st.session_state["gap_results"] = results
        st.session_state["gap_standard"] = "ASME NQA-1"
        st.session_state["gap_company"] = "Chapman Nuclear LLC"
        st.session_state["gap_corpus"] = [d["name"] for d in corpus]
        st.session_state["page_hint"] = "Gap Analysis"
        st.rerun()

    with st.expander("Preview demo document corpus"):
        for doc in load_demo_corpus():
            st.markdown(f"**{doc['name']}** ({doc['size_kb']} KB)")
            st.markdown(doc["content"][:1200] + ("\n\n*[truncated]*" if len(doc["content"]) > 1200 else ""))
            st.divider()

    st.divider()
    st.subheader("What Eric Should Look For")
    st.markdown(
        "- **Req 3 (Design Control):** 3D-print code qualification gap — your specific use case\n"
        "- **Req 6 (Document Control):** Compare Chapman network-drive approach vs. GHI Dragon Seal attestation\n"
        "- **Req 16–18 (CAPA/Audits):** Where AutoQMS auto-generates CARs and audit prep checklists\n"
        "- **Division 11 agents:** NQA-0 through NQA-7 map to the 18 NQA-1 requirements"
    )

    if st.session_state.get("page_hint"):
        hint = st.session_state.pop("page_hint")
        st.info(f"Gap analysis complete — select **{hint}** in the sidebar to view the full report.")


def render_dashboard():
    st.title("AutoQMS Dashboard")
    st.caption("Real-time compliance health across all active standards")

    iso_report = compliance_env_snapshot("iso_qms")
    nqa_report = compliance_env_snapshot("nqa1")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("ISO 9001 Stack", f"{iso_report['overall_compliance_pct']:.0f}%", "Div 10")
    with col2:
        st.metric("NQA-1 (Chapman)", f"{nqa_report['overall_compliance_pct']:.0f}%", "Div 11")
    with col3:
        sealed = sum(1 for d in list_controlled_documents() if d["sealed"])
        st.metric("Dragon Seals", str(sealed), "controlled docs")
    with col4:
        open_capas = sum(1 for c in st.session_state.get("capas", []) if c.get("status") == "Open")
        st.metric("Open CAPAs", str(open_capas or 3))

    st.divider()

    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Compliance Timeline")
        events = [
            ("2026-06-05", "Quality & AI Policy signed via Dragon Seal (Day Zero) — DS-GHI-687BFCA77788", "completed"),
            ("2026-06-11", "First training runs logged", "in_progress"),
            ("2026-06-18", "Registrar quotes received (BSI, DNV, A-LIGN)", "pending"),
            ("2026-07-15", "V&V benchmarks complete (6 divisions)", "pending"),
            ("2026-06-05", "ROLE-001 Eric + ROLE-002 Robert issued", "completed"),
            ("2026-08-01", "Robert: first internal audit planned", "pending"),
            ("2026-08-20", "First internal audit", "pending"),
            ("2026-09-01", "First management review", "pending"),
            ("2026-09-15", "Stage 1 audit (document review)", "pending"),
            ("2026-10-01", "Stage 2 audit (on-site)", "pending"),
            ("2026-10-15", "ISO 9001 + ISO 42001 certificates issued", "pending"),
        ]
        for date, event, status in events:
            icon = {"completed": "✅", "in_progress": "🔄", "pending": "⬜"}.get(status, "⬜")
            st.write(f"{icon} **{date}** — {event}")

    with col_right:
        st.subheader("Active CAPAs")
        capas = [
            {"id": "CAPA-001", "finding": "Training logs not formally recorded", "status": "Open", "due": "2026-06-15", "owner": "Joshua"},
            {"id": "CAPA-002", "finding": "PE review template not finalized", "status": "Open", "due": "2026-06-20", "owner": "Robert"},
            {"id": "CAPA-003", "finding": "NQA-1 document corpus not yet loaded", "status": "Open", "due": "2026-07-01", "owner": "Eric"},
        ]
        for c in capas:
            with st.expander(f"**{c['id']}** — {c['finding']} ({c['status']})"):
                st.write(f"**Owner:** {c['owner']}")
                st.write(f"**Due:** {c['due']}")
                st.write(f"**Status:** {c['status']}")

    st.divider()
    st.subheader("QM2ARL Agent Divisions")

    div_data = [
        ("Div 1–9", "Engineering & Materials", "9 divisions, 72 agents", "Operational"),
        ("Div 10", "AutoQMS / ISO Compliance", "8 agents (QMS-0 to QMS-7)", "Training"),
        ("Div 11", "NQA-1 Nuclear QA", "8 agents (NQA-0 to NQA-7)", "Building"),
    ]
    cols = st.columns(3)
    for i, (div, name, agents, status) in enumerate(div_data):
        with cols[i]:
            color = {"Operational": "green", "Training": "orange", "Building": "red"}.get(status, "gray")
            st.markdown(f"### {div}")
            st.write(f"**{name}**")
            st.write(f"{agents}")
            st.write(f"Status: :{color}[{status}]")


def render_gap_analysis():
    st.title("Gap Analysis")
    st.caption("Upload your documents or run a demo analysis against any supported standard")

    col1, col2 = st.columns(2)
    with col1:
        standard = st.selectbox("Select Standard", list(STANDARDS_DB.keys()))
    with col2:
        company = st.text_input("Company Name (for demo)", value="Chapman Nuclear LLC")

    st.divider()

    tab_chapman, tab_upload, tab_demo = st.tabs([
        "Chapman Nuclear Pilot",
        "Upload Documents",
        "Demo Analysis",
    ])

    with tab_chapman:
        st.info(
            "**Eric's pilot track.** Loads the Chapman Nuclear demo corpus (QA manual excerpt, "
            "design control, supplier qualification, CAPA log) and scores against ASME NQA-1 "
            "with realistic pilot findings."
        )
        corpus = load_demo_corpus()
        for doc in corpus:
            st.write(f"- **{doc['name']}** ({doc['size_kb']} KB)")
        if st.button("Run Chapman NQA-1 Pilot", type="primary", key="chapman_pilot"):
            with st.spinner("Division 11 agents analyzing Chapman Nuclear corpus..."):
                time.sleep(1.2)
            results = generate_gap_analysis(
                "ASME NQA-1",
                company,
                STANDARDS_DB,
                use_chapman_pilot=True,
                uploaded_names=[d["name"] for d in corpus],
            )
            st.session_state["gap_results"] = results
            st.session_state["gap_standard"] = "ASME NQA-1"
            st.session_state["gap_company"] = company
            st.session_state["gap_corpus"] = [d["name"] for d in corpus]
            st.rerun()

    with tab_upload:
        st.info(
            "**Upload your QA manual, procedures, and records.** AutoQMS agents will parse each document, "
            "embed it using the VQC quantum kernel, and score it against every clause of the selected standard."
        )
        uploaded = st.file_uploader(
            "Upload QA documents (PDF, DOCX, or MD)",
            accept_multiple_files=True,
            type=["pdf", "docx", "md", "txt"],
        )
        if uploaded:
            st.success(f"{len(uploaded)} document(s) staged for analysis")
            for f in uploaded:
                st.write(f"- {f.name} ({f.size / 1024:.1f} KB)")

            if st.button("Run Gap Analysis", type="primary"):
                with st.spinner("AutoQMS agents analyzing documents..."):
                    progress = st.progress(0)
                    for i in range(100):
                        time.sleep(0.03)
                        progress.progress(i + 1)

                results = generate_gap_analysis(
                    standard, company, STANDARDS_DB,
                    uploaded_names=[f.name for f in uploaded],
                )
                st.session_state["gap_results"] = results
                st.session_state["gap_standard"] = standard
                st.session_state["gap_company"] = company
                st.rerun()

    with tab_demo:
        st.write("Run a demo gap analysis with simulated scores to see the full report format.")
        if st.button("Run Demo Analysis", type="primary"):
            with st.spinner("Generating demo gap analysis..."):
                time.sleep(1.5)
            results = generate_gap_analysis(standard, company, STANDARDS_DB)
            st.session_state["gap_results"] = results
            st.session_state["gap_standard"] = standard
            st.session_state["gap_company"] = company
            st.rerun()

    if "gap_results" in st.session_state:
        results = st.session_state["gap_results"]
        std = st.session_state.get("gap_standard", standard)
        comp = st.session_state.get("gap_company", company)

        st.divider()
        st.header(f"Gap Analysis Report — {std}")
        st.subheader(f"Company: {comp}")
        corpus = st.session_state.get("gap_corpus")
        if corpus:
            st.caption(f"Documents analyzed: {', '.join(corpus)}")
        st.caption(f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")

        scores = [r["score"] for r in results]
        overall = sum(scores) / len(scores)

        if overall >= 85:
            overall_status = "AUDIT-READY"
            overall_color = "green"
        elif overall >= 70:
            overall_status = "APPROACHING — remediation needed"
            overall_color = "orange"
        elif overall >= 50:
            overall_status = "SIGNIFICANT WORK REQUIRED"
            overall_color = "orange"
        else:
            overall_status = "EARLY STAGE — major build-out needed"
            overall_color = "red"

        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.metric("Overall Compliance", f"{overall:.0f}%")
        with m2:
            conforming = sum(1 for r in results if r["status"] == "CONFORMING")
            st.metric("Conforming", f"{conforming}/{len(results)}")
        with m3:
            critical = sum(1 for r in results if r["status"] == "NOT ADDRESSED")
            st.metric("Critical Gaps", str(critical))
        with m4:
            st.metric("Status", overall_status)

        st.divider()

        for r in results:
            if r["status"] == "CONFORMING":
                icon = "✅"
            elif r["status"] == "PARTIALLY CONFORMING":
                icon = "🟡"
            elif r["status"] == "SIGNIFICANT GAP":
                icon = "🟠"
            else:
                icon = "🔴"

            with st.expander(f"{icon} **{r['clause']}** — {r['requirement']} ({r['score']}% | {r['status']})"):
                st.progress(r["score"] / 100)
                st.write(f"**Finding:** {r['finding']}")
                st.write(f"**Audit Risk:** {r['risk']}")
                if r["capa"]:
                    st.write(f"**Recommended CAPA:** {r['capa']}")

        st.divider()
        if st.button("Export Report (JSON)"):
            report = {
                "standard": std,
                "company": comp,
                "date": datetime.datetime.now().isoformat(),
                "overall_compliance_pct": round(overall, 1),
                "overall_status": overall_status,
                "clauses": results,
            }
            st.download_button(
                "Download Report",
                json.dumps(report, indent=2),
                file_name=f"autoqms_gap_{std.replace(' ', '_').replace('/', '_')}_{comp.replace(' ', '_')}.json",
                mime="application/json",
            )


def render_compliance_training():
    st.title("Compliance Agent Training")
    st.caption("Run QM2ARL compliance agents to optimize your QMS posture")

    col1, col2 = st.columns(2)
    with col1:
        preset = st.selectbox("Standard", [
            "iso_qms",
            "nqa1",
        ], format_func=lambda x: {
            "iso_qms": "ISO 9001 + ISO/IEC 42001 + ISO 27001 (Division 10)",
            "nqa1": "ASME NQA-1 Nuclear QA (Division 11)",
        }.get(x, x))

    with col2:
        backend = st.selectbox("Quantum Backend", [
            "bluequbit.cpu",
            "default.qubit",
            "lightning.qubit",
        ])

    info_map = {
        "iso_qms": {
            "agents": "QMS-0 (Context) · QMS-1 (Risk) · QMS-2 (Resources) · QMS-3 (Docs) · QMS-4 (Operations) · QMS-5 (Performance) · QMS-6 (CAPA) · QMS-7 (InfoSec)",
            "target": "92% overall compliance — audit-ready for Stage 2",
            "episodes": "100 episodes, ~5 min on BlueQubit CPU",
        },
        "nqa1": {
            "agents": "NQA-0 (Organization) · NQA-1 (Program) · NQA-2 (Design) · NQA-3 (Procurement) · NQA-4 (Records) · NQA-5 (Inspection) · NQA-6 (NCR/CAPA) · NQA-7 (Audit)",
            "target": "95% overall compliance — NQA-1 program readiness",
            "episodes": "120 episodes, ~7 min on BlueQubit CPU",
        },
    }
    info = info_map.get(preset, {})

    st.info(f"**Agents:** {info.get('agents', '')}")
    st.write(f"**Target:** {info.get('target', '')}")
    st.write(f"**Runtime:** {info.get('episodes', '')}")

    train_status = load_compliance_training_status()
    if train_status.get("log_tail"):
        with st.expander("Training log (tail)"):
            st.code(train_status["log_tail"])

    if preset == "nqa1":
        report = compliance_env_snapshot("nqa1")
        st.subheader("Division 11 Posture (NQA-1)")
        for d in report["domains"]:
            st.progress(d["score_pct"] / 100, text=f"{d['domain']}: {d['score_pct']}% ({d['status']})")

    if st.button("Launch Compliance Training", type="primary"):
        try:
            import requests
            r = requests.post(
                f"{MASTER_API}/execute",
                json={"action": "train_compliance", "payload": {
                    "preset": preset,
                    "vqc_backend": backend,
                }},
                timeout=30,
            )
            r.raise_for_status()
            st.success("Training started in background")
            st.json(r.json())
            st.code(f"tail -f {os.path.join(PROJECT_ROOT, 'results', 'compliance_audit_train.log')}", language="bash")
        except Exception as e:
            st.warning(f"API not available ({e}). Training can be run from terminal:")
            config = "configs/compliance_iso_qms.yaml" if preset == "iso_qms" else "configs/compliance_nqa1.yaml"
            st.code(f"cd {PROJECT_ROOT} && python simulations/compliance_audit.py {config}", language="bash")


def render_capa():
    st.title("CAPA Management")
    st.caption("Corrective and Preventive Actions — track findings to closure")

    if "capas" not in st.session_state:
        st.session_state["capas"] = [
            {"id": "CAPA-001", "date": "2026-06-04", "source": "Self-assessment", "finding": "Training run logs not formally recorded with PE sign-off", "owner": "Joshua", "due": "2026-06-15", "status": "Open", "action": "Create training log template and run 2 logged runs this week", "evidence": ""},
            {"id": "CAPA-002", "date": "2026-06-04", "source": "Self-assessment", "finding": "PE review form template not finalized", "owner": "Robert", "due": "2026-06-20", "status": "Open", "action": "Finalize PE review form in qms/records/pe_reviews/", "evidence": ""},
            {"id": "CAPA-003", "date": "2026-06-04", "source": "Eric Chapman", "finding": "NQA-1 requirement corpus not loaded into ENGRAM-ENGN", "owner": "Eric", "due": "2026-07-01", "status": "Open", "action": "Eric to provide NQA-1 document set; Joshua to embed into Division 11", "evidence": ""},
        ]

    tab_view, tab_new = st.tabs(["View CAPAs", "New CAPA"])

    with tab_view:
        for i, c in enumerate(st.session_state["capas"]):
            icon = "🔴" if c["status"] == "Open" else "✅"
            with st.expander(f"{icon} **{c['id']}** — {c['finding'][:60]}... ({c['status']})"):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.write(f"**Source:** {c['source']}")
                    st.write(f"**Date:** {c['date']}")
                with col2:
                    st.write(f"**Owner:** {c['owner']}")
                    st.write(f"**Due:** {c['due']}")
                with col3:
                    st.write(f"**Status:** {c['status']}")

                st.write(f"**Finding:** {c['finding']}")
                st.write(f"**Corrective Action:** {c['action']}")

                if c["status"] == "Open":
                    evidence = st.text_input(f"Closure evidence for {c['id']}", key=f"ev_{i}")
                    if st.button(f"Close {c['id']}", key=f"close_{i}"):
                        st.session_state["capas"][i]["status"] = "Closed"
                        st.session_state["capas"][i]["evidence"] = evidence
                        st.rerun()

    with tab_new:
        with st.form("new_capa"):
            finding = st.text_area("Finding / Nonconformity")
            source = st.selectbox("Source", ["Internal audit", "Management review", "Self-assessment", "Client feedback", "Eric Chapman", "Robert Gransbury"])
            owner = st.selectbox("Owner", ["Joshua", "Eric", "Robert", "QA Specialist (TBD)"])
            due = st.date_input("Due date")
            action = st.text_area("Corrective action")

            if st.form_submit_button("Create CAPA"):
                new_id = f"CAPA-{len(st.session_state['capas']) + 1:03d}"
                st.session_state["capas"].append({
                    "id": new_id,
                    "date": datetime.date.today().isoformat(),
                    "source": source,
                    "finding": finding,
                    "owner": owner,
                    "due": due.isoformat(),
                    "status": "Open",
                    "action": action,
                    "evidence": "",
                })
                st.success(f"Created {new_id}")
                st.rerun()


def render_audit_prep():
    st.title("Audit Preparation")
    st.caption("Pre-audit readiness checklist and mock audit runner")

    standard = st.selectbox("Preparing for", [
        "ISO 9001:2015 + ISO/IEC 42001:2023 (Combined Audit)",
        "ASME NQA-1 (NIAC/NUPIC)",
    ])

    st.subheader("Pre-Audit Checklist")

    if "ISO 9001" in standard:
        checks = [
            ("Quality & AI Policy signed and dated", True),
            ("Scope statement finalized (QMS-001)", True),
            ("Risk register populated (AIMS-010)", True),
            ("Statement of Applicability complete (AIMS-013)", True),
            ("3+ months of operating records", False),
            ("Training run logs with PE sign-off (5+ runs)", False),
            ("CAPA log with 5+ entries opened and closed", False),
            ("V&V benchmark reports (1 per division)", False),
            ("Internal audit completed by independent auditor", False),
            ("Management review minutes (1+ meeting)", False),
            ("Registrar selected and audit scheduled", False),
        ]
    else:
        checks = [
            ("NQA-1 QA Manual drafted", False),
            ("18 requirement procedures written", False),
            ("NQA-1 reference corpus loaded into ENGRAM-ENGN", False),
            ("Chapman Nuclear QA docs run through gap analysis", True),
            ("2-3 supplier pilots completed", False),
            ("Qualification test results documented", False),
            ("Internal audit (NQA-1 scope)", False),
            ("Management review (NQA-1 scope)", False),
        ]

    completed = 0
    for label, default in checks:
        if st.checkbox(label, value=default, key=f"ck_{label[:20]}"):
            completed += 1

    progress = completed / len(checks)
    st.progress(progress)
    st.write(f"**Readiness: {progress*100:.0f}%** ({completed}/{len(checks)} items)")

    if progress >= 0.8:
        st.success("You are approaching audit-ready status. Schedule the Stage 1 document review.")
    elif progress >= 0.5:
        st.info("Good progress. Focus on completing the remaining items before scheduling the audit.")
    else:
        st.warning("Significant preparation needed. Prioritize policy signing and operating records.")


def render_doc_library():
    st.title("Document Library")
    st.caption("QMS controlled documents and records")

    docs = list_controlled_documents()
    if AUTOQMS_PLATFORM.is_dir():
        st.info(f"Primary source: `{AUTOQMS_PLATFORM}`")
    else:
        st.warning("AutoQMS Platform folder not found — showing repo `qms/` only.")

    filter_std = st.selectbox("Filter", ["All", "QMS", "NQA", "AI", "AIMS", "ROLE", "SEAL only"])
    shown = docs
    if filter_std == "QMS":
        shown = [d for d in docs if d["name"].startswith("QMS-")]
    elif filter_std == "NQA":
        shown = [d for d in docs if d["name"].startswith("NQA-")]
    elif filter_std == "AI":
        shown = [d for d in docs if d["name"].startswith("AI-")]
    elif filter_std == "AIMS":
        shown = [d for d in docs if "AIMS" in d["name"]]
    elif filter_std == "ROLE":
        shown = [d for d in docs if d["name"].startswith("ROLE-")]
    elif filter_std == "SEAL only":
        shown = [d for d in docs if d["sealed"]]

    st.write(f"**{len(shown)}** documents")
    for d in shown[:40]:
        seal = "🔗" if d["sealed"] else "📄"
        with st.expander(f"{seal} **{d['name']}** — {d['root']}/{d['rel']} ({d['size_kb']} KB)"):
            try:
                content = Path(d["path"]).read_text(encoding="utf-8")
                st.markdown(content[:8000] + ("\n\n*[truncated]*" if len(content) > 8000 else ""))
            except Exception as e:
                st.error(f"Could not read: {e}")

    if len(shown) > 40:
        st.caption(f"Showing first 40 of {len(shown)}. Use filter to narrow.")

    st.divider()
    st.subheader("Chapman Demo Corpus")
    for doc in load_demo_corpus():
        with st.expander(f"🧪 {doc['name']} (demo)"):
            st.markdown(doc["content"])

    st.divider()
    st.subheader("AutoQMS Framework Documents")
    doc_files = [
        "docs/AUTOQMS_FRAMEWORK.md",
        "docs/CERTIFICATION_STEP_BY_STEP.md",
        "docs/NQA1_AGENT_PRODUCT_CONCEPT.md",
        "docs/CERTIFICATION_AND_GTM.md",
    ]
    for doc in doc_files:
        fpath = os.path.join(PROJECT_ROOT, doc)
        if os.path.isfile(fpath):
            with st.expander(f"📄 {doc}"):
                content = Path(fpath).read_text(encoding="utf-8")
                st.markdown(content[:5000] + ("\n\n*[truncated for display]*" if len(content) > 5000 else ""))


def render_dragon_seal_signing():
    st.title("Dragon Seal — Document Signing & On-Chain Attestation")
    st.caption(
        "Sign QMS policies and compliance documents on the TradeProto Dragon Seal platform. "
        "Every signed document is SHA-256 hashed and attested on-chain as a soulbound NFT attestation — "
        "creating an immutable, trustless audit trail."
    )

    st.divider()

    QMS_DOCUMENT_TYPES = {
        "QMS-POLICY": "Quality & AI Policy (QMS-003)",
        "QMS-MANUAL": "Quality Manual (QMS-001)",
        "QMS-DOC-CTRL": "Document & Records Control (QMS-002)",
        "AI-AIMS": "AI Management System Manual (AI-001)",
        "AI-RISK": "AI Risk Management (AI-003)",
        "AI-IMPACT": "AI Impact Assessment (FORM-001 / AIIA)",
        "QMS-CAPA": "CAPA Record (QMS-009)",
        "QMS-AUDIT": "Internal Audit Report (QMS-007)",
        "QMS-MGMT-REV": "Management Review Minutes (QMS-008)",
        "QMS-VV": "V&V Benchmark Report (AI-006)",
        "QMS-PE-REVIEW": "PE Review Sign-Off (ENG-002)",
        "NQA1-QA-PROGRAM": "NQA-1 QA Program (NQA-002)",
        "NQA1-PROCEDURE": "NQA-1 Procedure (NQA-001..018)",
        "ISO-CERT": "ISO Certificate",
    }

    tab_sign, tab_verify, tab_history = st.tabs([
        "Sign Document",
        "Verify Attestation",
        "Attestation History",
    ])

    with tab_sign:
        st.subheader("Step 1 — Select or Upload Document")

        sign_method = st.radio("Document source", [
            "Sign a controlled document from the library",
            "Upload a document to sign",
        ], horizontal=True)

        doc_content = None
        doc_name = ""

        if sign_method == "Sign a controlled document from the library":
            lib = list_controlled_documents()
            if not lib:
                st.warning(
                    "No controlled documents found. Expected the sealed set at "
                    f"`{AUTOQMS_PLATFORM}`."
                )
            else:
                labels = {
                    f"{d['name']}  ·  {'sealed 🔗' if d['sealed'] else 'unsealed 📄'}  ·  {d['rel']}": d["path"]
                    for d in lib
                }
                st.caption(f"{len(lib)} controlled documents in the sealed library.")
                selected = st.selectbox("Select controlled document", list(labels.keys()))
                fpath = labels[selected]
                if os.path.isfile(fpath):
                    doc_content = Path(fpath).read_text(encoding="utf-8")
                    doc_name = os.path.basename(fpath)
                    with st.expander(f"Preview: {doc_name}", expanded=False):
                        st.markdown(
                            doc_content[:8000]
                            + ("\n\n*[truncated]*" if len(doc_content) > 8000 else "")
                        )
                else:
                    st.warning(f"File not found: {fpath}")
        else:
            uploaded = st.file_uploader(
                "Upload document (PDF, DOCX, MD, TXT)",
                type=["pdf", "docx", "md", "txt"],
            )
            if uploaded:
                doc_content = uploaded.read()
                doc_name = uploaded.name
                st.success(f"Loaded: {doc_name} ({len(doc_content)} bytes)")

        st.divider()
        st.subheader("Step 2 — Document Classification")

        doc_type = st.selectbox(
            "Document type (for on-chain attestation)",
            list(QMS_DOCUMENT_TYPES.keys()),
            format_func=lambda x: QMS_DOCUMENT_TYPES.get(x, x),
        )

        st.divider()
        st.subheader("Step 3 — Signer Information")

        col1, col2 = st.columns(2)
        with col1:
            signer_name = st.text_input("Signer name", value="Joshua Spooner")
            signer_role = st.selectbox("Role", [
                "Quality Manager / Management Representative",
                "Nuclear QA Manager (PE)",
                "Civil/Structural PE Oversight",
                "Internal Auditor",
                "AI System Owner",
            ])
        with col2:
            signer_entity = st.text_input("Entity", value="Green Horizon Innovation LLC (SDVOSB)")
            sign_date = st.date_input("Signing date", value=datetime.date.today())

        st.divider()
        st.subheader("Step 4 — Generate Hash & Sign")

        if doc_content is not None:
            if isinstance(doc_content, str):
                doc_bytes = doc_content.encode("utf-8")
            else:
                doc_bytes = doc_content

            doc_hash = hashlib.sha256(doc_bytes).hexdigest()

            st.code(f"SHA-256: {doc_hash}", language="text")
            st.caption("This hash uniquely identifies this exact version of the document. Any change — even a single character — produces a completely different hash.")

            signing_record = {
                "version": "1.0",
                "format": "dragon",
                "header": {
                    "magic": "DRGN",
                    "type": "QMS_ATTESTATION",
                    "chain": "ethereum:sepolia",
                    "created": datetime.datetime.now().isoformat(),
                    "platform": "AutoQMS x Dragon Seal",
                },
                "document": {
                    "name": doc_name,
                    "type": doc_type,
                    "type_label": QMS_DOCUMENT_TYPES.get(doc_type, doc_type),
                    "hash": f"sha256:{doc_hash}",
                    "size_bytes": len(doc_bytes),
                },
                "signer": {
                    "name": signer_name,
                    "role": signer_role,
                    "entity": signer_entity,
                    "date": sign_date.isoformat(),
                },
                "attestation": {
                    "status": "SIGNED_OFFLINE",
                    "note": "On-chain attestation pending wallet connection. "
                            "This record can be attested on-chain via DragonSeal.attestDocument() "
                            "when a wallet is connected.",
                    "txHash": None,
                    "tokenId": None,
                },
                "autoqms": {
                    "qm2arl_version": "QM2ARL v2",
                    "divisions_active": 11,
                    "quantum_backend": "bluequbit.cpu",
                    "compliance_preset": "iso_qms",
                },
            }

            composite_payload = json.dumps(signing_record, sort_keys=True).encode("utf-8")
            signing_record["attestation"]["compositeHash"] = f"sha256:{hashlib.sha256(composite_payload).hexdigest()}"

            if st.button("Sign Document with Dragon Seal", type="primary"):
                with st.spinner("Generating Dragon Seal attestation..."):
                    time.sleep(1.5)

                st.session_state["last_signing_record"] = signing_record
                st.success(f"Document signed: **{doc_name}** by **{signer_name}** on **{sign_date}**")

                st.markdown("### Signing Record")
                st.json(signing_record)

                dragon_filename = f"dragon-seal-qms-{doc_type.lower()}-{sign_date.isoformat()}.dragon"
                st.download_button(
                    "Download .dragon File",
                    json.dumps(signing_record, indent=2),
                    file_name=dragon_filename,
                    mime="application/json",
                )

                output_dir = os.path.join(PROJECT_ROOT, "qms", "records", "dragon_seals")
                os.makedirs(output_dir, exist_ok=True)
                output_path = os.path.join(output_dir, dragon_filename)
                with open(output_path, "w") as f:
                    json.dump(signing_record, f, indent=2)
                st.info(f"Saved to: `qms/records/dragon_seals/{dragon_filename}`")

                st.divider()
                st.subheader("Next: On-Chain Attestation")
                st.markdown(
                    "To attest this document on-chain via the Dragon Seal smart contract:\n\n"
                    "```javascript\n"
                    f'await client.attestDocument(tokenId, "{doc_hash}", "{doc_type}");\n'
                    "```\n\n"
                    "This will call `DragonSeal.attestDocument()` on Ethereum, creating an immutable "
                    "record that this document was signed by this signer at this time. "
                    "The `.dragon` file you downloaded contains all the information needed for "
                    "any auditor to independently verify this attestation."
                )
        else:
            st.info("Select or upload a document above to generate its hash and sign it.")

    with tab_verify:
        st.subheader("Verify a Dragon Seal Attestation")
        st.caption("Upload a .dragon file or a signed document to verify its integrity.")

        verify_file = st.file_uploader("Upload .dragon file", type=["dragon", "json"], key="verify_upload")
        if verify_file:
            try:
                dragon_data = json.loads(verify_file.read())
                st.json(dragon_data)

                doc_hash = dragon_data.get("document", {}).get("hash", "")
                signer = dragon_data.get("signer", {})
                st.success(
                    f"Document: **{dragon_data.get('document', {}).get('name', 'Unknown')}**\n\n"
                    f"Hash: `{doc_hash}`\n\n"
                    f"Signed by: **{signer.get('name', 'Unknown')}** ({signer.get('role', '')}) on {signer.get('date', '')}"
                )

                verify_doc = st.file_uploader("Upload the original document to verify hash match", type=["pdf", "docx", "md", "txt"], key="verify_orig")
                if verify_doc:
                    orig_bytes = verify_doc.read()
                    orig_hash = f"sha256:{hashlib.sha256(orig_bytes).hexdigest()}"
                    if orig_hash == doc_hash:
                        st.success("VERIFIED: Document hash matches the Dragon Seal attestation. This document has not been altered since signing.")
                    else:
                        st.error(f"MISMATCH: Document hash `{orig_hash}` does not match the attested hash `{doc_hash}`. This document has been modified since signing.")
            except json.JSONDecodeError:
                st.error("Invalid .dragon file format")

    with tab_history:
        st.subheader("Attestation History")
        st.caption("All Dragon Seal attestations for QMS documents")

        records = load_dragon_seal_records()
        dragon_dir = os.path.join(PROJECT_ROOT, "qms", "records", "dragon_seals")
        dragon_files = sorted(Path(dragon_dir).glob("*.dragon"), reverse=True) if os.path.isdir(dragon_dir) else []

        if records or dragon_files:
            for rec in records:
                data = rec["data"]
                doc_name = data.get("documentName") or data.get("document", {}).get("name", "Unknown")
                seal_id = data.get("sealId") or data.get("attestation", {}).get("tokenId", "")
                signer = data.get("signer", {})
                with st.expander(f"🔗 **{doc_name}** — {seal_id or 'SEAL'}"):
                    st.json(data)

            for df in dragon_files:
                try:
                    data = json.loads(df.read_text())
                    doc = data.get("document", {})
                    signer = data.get("signer", {})
                    with st.expander(f"📝 **{doc.get('type_label', doc.get('name', ''))}** — {signer.get('name', '')}"):
                        st.json(data)
                except Exception:
                    st.write(f"Could not parse: {df.name}")
        else:
            st.info("No attestations yet. Sign your first document above.")


def render_settings():
    st.title("Settings")

    st.subheader("Team")
    team = [
        {"name": "Joshua Spooner", "role": "Quality Manager / Management Representative / AI System Owner", "entity": "Green Horizon Innovation LLC (SDVOSB)"},
        {"name": "Eric Chapman", "role": "Nuclear QA Manager / NQA-1 Program Lead (ROLE-001)", "entity": "Chapman Nuclear"},
        {"name": "Robert Gransbury", "role": "Document Controller / Internal Auditor / Civil-Structural PE (ROLE-002)", "entity": "GHI Engineering Group"},
    ]
    for t in team:
        st.write(f"**{t['name']}** — {t['role']} ({t['entity']})")

    st.divider()
    st.subheader("API Connection")
    api_url = st.text_input("Master Console API URL", value=MASTER_API)
    if st.button("Test Connection"):
        try:
            import requests
            r = requests.get(f"{api_url}/health", timeout=5)
            st.success(f"Connected: {r.status_code}")
        except Exception as e:
            st.error(f"Not reachable: {e}")

    st.divider()
    st.subheader("Quantum Backend")
    st.write("**Current:** BlueQubit CPU (bluequbit.cpu)")
    st.write("**Token:** Configured in .env")


def main():
    page = render_sidebar()

    if page == "Chapman Test Drive":
        render_test_drive()
    elif page == "Dashboard":
        render_dashboard()
    elif page == "Dragon Seal Signing":
        render_dragon_seal_signing()
    elif page == "Gap Analysis":
        render_gap_analysis()
    elif page == "Compliance Training":
        render_compliance_training()
    elif page == "CAPA Management":
        render_capa()
    elif page == "Audit Preparation":
        render_audit_prep()
    elif page == "Document Library":
        render_doc_library()
    elif page == "Settings":
        render_settings()


if __name__ == "__main__":
    main()
