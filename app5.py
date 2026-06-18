"""
Impact Radar — Enterprise Software Change Impact Analysis Platform
------------------------------------------------------------------
Run:  streamlit run app5.py
Keep the .streamlit/config.toml next to this file (it sets the dark theme),
though the app also forces its own dark theme via injected CSS.

Requires sibling modules:
  - scanner_service.scan_project(folder) -> {module: [deps]}
  - project_service.{load_projects, create_project, add_module, add_dependency}
"""

import os
import zipfile
from collections import deque, defaultdict
from datetime import datetime

import streamlit as st

from scanner_service import scan_project
from project_service import (
    load_projects,
    create_project,
    add_module,
    add_dependency,
)
from report_service import build_pdf_report

st.set_page_config(page_title="Impact Radar", page_icon="◎", layout="wide")

# ---------------------------------------------------------------------------
# Domain model — module -> modules it DEPENDS ON  (loaded dynamically)
# ---------------------------------------------------------------------------
PROJECTS = load_projects()

ACCENT = "#6366f1"
BORDER = "#1f2937"
MUTED = "#7b8aa3"
TEXT = "#e5e9f0"

# ---------------------------------------------------------------------------
# Impact engine
# ---------------------------------------------------------------------------
def reverse_dependents(modules):
    dependents = defaultdict(set)
    for module, deps in modules.items():
        for dep in deps:
            dependents[dep].add(module)
    return dependents


def compute_impact(modules, changed):
    dependents = reverse_dependents(modules)
    direct = set(dependents.get(changed, set()))
    impacted, queue = set(), deque([changed])
    while queue:
        cur = queue.popleft()
        for dep in dependents.get(cur, set()):
            if dep not in impacted:
                impacted.add(dep)
                queue.append(dep)
    return direct, impacted - direct, impacted


def assess_risk(impacted, total):
    ratio = len(impacted) / max(total - 1, 1)
    if ratio >= 0.5:
        return "HIGH", "#ef4444", ratio
    if ratio >= 0.25:
        return "MEDIUM", "#f59e0b", ratio
    return "LOW", "#22c55e", ratio


def build_dot(modules, changed, direct, indirect):
    """Size-capped DOT so nodes stay compact under width='content'."""
    out = [
        "digraph G {",
        '  graph [rankdir=LR bgcolor="transparent" nodesep="0.3"'
        ' ranksep="0.6" pad="0.25" size="9,4.2" ratio="compress"];',
        '  node [shape=box style="rounded,filled" fontname="Inter"'
        ' fontsize="11" height="0.45" margin="0.16,0.04" penwidth="1.2"];',
        '  edge [color="#3f4a5f" arrowsize="0.7" penwidth="1.0"];',
    ]
    for module in modules:
        if module == changed:
            fill, font, bd = ACCENT, "#ffffff", "#a5b4fc"
        elif module in direct:
            fill, font, bd = "#ef4444", "#ffffff", "#fca5a5"
        elif module in indirect:
            fill, font, bd = "#7f1d1d", "#fecaca", "#dc2626"
        else:
            fill, font, bd = "#1b2434", MUTED, "#2b364a"
        out.append(f'  "{module}" [fillcolor="{fill}" fontcolor="{font}" color="{bd}"];')
    for module, deps in modules.items():
        for dep in deps:
            out.append(f'  "{dep}" -> "{module}";')
    out.append("}")
    return "\n".join(out)


def affected_rows_html(direct, indirect):
    """Single-line-safe inline-styled rows (no leak risk)."""
    def row(name, label, bg, fg):
        return (
            f'<div style="display:flex;justify-content:space-between;'
            f'align-items:center;padding:8px 2px;border-bottom:1px solid {BORDER};">'
            f'<span style="color:{TEXT};font-size:13px;font-weight:500;">{name}</span>'
            f'<span style="background:{bg};color:{fg};font-size:11px;font-weight:600;'
            f'padding:3px 9px;border-radius:6px;">{label}</span></div>'
        )
    rows = [row(m, "Direct", "rgba(239,68,68,0.15)", "#f87171") for m in sorted(direct)]
    rows += [row(m, "Indirect", "rgba(245,158,11,0.15)", "#fbbf24") for m in sorted(indirect)]
    if not rows:
        return f'<div style="color:{MUTED};font-size:13px;padding:6px 0;">No downstream modules affected — safe to change.</div>'
    return "".join(rows)


# ---------------------------------------------------------------------------
# Self-contained dark theme — ONE block, NO blank lines (blank lines break it)
# ---------------------------------------------------------------------------
st.markdown(
    "<style>"
    "@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');"
    "html, body, [class*='css'] { font-family: 'Inter', sans-serif; }"
    ".block-container { padding-top: 2rem; padding-bottom: 3rem; max-width: 1320px; }"
    "#MainMenu, footer { visibility: hidden; }"
    ".stApp { background-color: #0b0f17; color: #e5e9f0; }"
    "[data-testid='stHeader'] { background-color: #0b0f17; }"
    "[data-testid='stSidebar'] { background-color: #0e1421; }"
    "[data-testid='stSidebar'] * { color: #e5e9f0; }"
    "[data-testid='stMetricValue'] { color: #e5e9f0; font-size: 1.7rem; font-weight: 700; }"
    "[data-testid='stMetricLabel'], [data-testid='stMetricLabel'] * { color: #7b8aa3; }"
    "[data-testid='stWidgetLabel'], [data-testid='stWidgetLabel'] * { color: #7b8aa3; }"
    "div[data-baseweb='select'] > div { background-color: #111726; border-color: #1f2937; color: #e5e9f0; }"
    "div[data-baseweb='select'] svg { fill: #7b8aa3; }"
    "ul[role='listbox'] { background-color: #111726; }"
    "ul[role='listbox'] li { color: #e5e9f0; }"
    ".stTextInput input, .stTextArea textarea { background-color: #111726; color: #e5e9f0; border-color: #1f2937; }"
    # --- Buttons: keep them visible & legible on the dark theme ---
    # The download button in particular was rendering with dark text on a
    # dark/transparent background, making it effectively invisible.
    ".stButton > button, .stDownloadButton > button {"
    " background-color: #6366f1; color: #ffffff; border: 1px solid #6366f1;"
    " font-weight: 600; border-radius: 8px; padding: 0.45rem 1rem; }"
    ".stButton > button:hover, .stDownloadButton > button:hover {"
    " background-color: #4f54d6; border-color: #4f54d6; color: #ffffff; }"
    ".stButton > button:active, .stButton > button:focus,"
    ".stDownloadButton > button:active, .stDownloadButton > button:focus {"
    " color: #ffffff; box-shadow: 0 0 0 2px rgba(99,102,241,0.4); }"
    ".stButton > button *, .stDownloadButton > button * { color: #ffffff; }"
    "</style>",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### ◎ Impact Radar")
    st.caption("Change Impact Analysis")
    st.divider()
    page = st.radio("Navigation", ["Dashboard", "Projects", "Reports"],
                    label_visibility="collapsed")

# ===========================================================================
# DASHBOARD
# ===========================================================================
if page == "Dashboard":
    st.markdown(
        f"<div style='color:{ACCENT};font-size:12px;font-weight:600;"
        "letter-spacing:1.2px;text-transform:uppercase;'>Change Impact Analysis</div>"
        f"<div style='font-size:30px;font-weight:700;color:{TEXT};"
        "letter-spacing:-0.5px;'>Impact Radar</div>"
        f"<div style='color:{MUTED};font-size:14px;margin-bottom:8px;'>"
        "Trace how a single module change ripples through your system before you ship it.</div>",
        unsafe_allow_html=True,
    )

    # Empty-state guard: load_projects() can return {}
    if not PROJECTS:
        st.info("No projects yet. Add one from the **Projects** page to start analyzing.")
        st.stop()

    # --- Control bar ---
    with st.container(border=True):
        c1, c2, c3 = st.columns([2, 2, 1], vertical_alignment="bottom")
        with c1:
            project = st.selectbox("Project", list(PROJECTS.keys()))
        modules = PROJECTS[project]
        with c2:
            changed = st.selectbox("Changed module", list(modules.keys()))
        with c3:
            analyze = st.button("Analyze impact", width="stretch", type="primary")

    # Guard: selected project may have no modules yet
    if not modules:
        st.warning("This project has no modules yet — add some on the **Projects** page.")
        st.stop()

    # compute_impact is O(V+E) and cheap, so we recompute from the live
    # selection every run. The dashboard always reflects the dropdowns.
    direct, indirect, impacted = compute_impact(modules, changed)
    level, color, ratio = assess_risk(impacted, len(modules))

    # "Analyze impact" (or first load) commits a snapshot for the Reports page.
    if analyze or "report" not in st.session_state:
        st.session_state.report = {
            "project": project,
            "changed_module": changed,
            "direct": sorted(direct),
            "indirect": sorted(indirect),
            "total_impacted": len(impacted),
            "risk": level,
            "generated_at": datetime.now().strftime("%d-%b-%Y %I:%M %p"),
            # snapshot the dependency map so the PDF can redraw the graph
            # exactly as it was when the analysis ran
            "modules": {m: list(deps) for m, deps in modules.items()},
        }

    # --- KPI strip ---
    k1, k2, k3, k4 = st.columns(4)
    for col, (label, value) in zip(
        (k1, k2, k3, k4),
        [("Total modules", len(modules)),
         ("Direct dependents", len(direct)),
         ("Indirect dependents", len(indirect)),
         ("Total impacted", len(impacted))],
    ):
        with col:
            with st.container(border=True):
                st.metric(label, value)

    st.write("")

    # --- Main: graph (hero, left) + right rail (risk + affected) ---
    left, right = st.columns([2.3, 1], gap="medium")

    with left:
        with st.container(border=True):
            st.markdown(f"<b style='color:{TEXT};'>Dependency graph</b>", unsafe_allow_html=True)
            st.graphviz_chart(build_dot(modules, changed, direct, indirect), width="content")
            st.markdown(
                "<div style='color:#7b8aa3;font-size:12px;margin-top:4px;'>"
                "<span style='color:#a5b4fc;'>●</span> changed &nbsp;"
                "<span style='color:#ef4444;'>●</span> direct &nbsp;"
                "<span style='color:#dc2626;'>●</span> indirect &nbsp;"
                "<span style='color:#7b8aa3;'>●</span> unaffected</div>",
                unsafe_allow_html=True,
            )

    with right:
        with st.container(border=True):
            st.markdown(f"<b style='color:{TEXT};'>Risk assessment</b>", unsafe_allow_html=True)
            st.markdown(
                f"<div style='margin:10px 0 6px 0;'><span style='background:{color}22;"
                f"color:{color};padding:6px 16px;border-radius:8px;font-weight:700;"
                f"font-size:18px;letter-spacing:0.5px;'>{level}</span></div>"
                f"<div style='color:{MUTED};font-size:13px;'>Blast radius: "
                f"{len(impacted)} of {len(modules) - 1} modules ({ratio*100:.0f}%)</div>",
                unsafe_allow_html=True,
            )
        st.write("")
        with st.container(border=True):
            st.markdown(f"<b style='color:{TEXT};'>Affected modules</b>", unsafe_allow_html=True)
            st.markdown(affected_rows_html(direct, indirect), unsafe_allow_html=True)

# ===========================================================================
# PROJECTS
# ===========================================================================
elif page == "Projects":
    st.title("Projects")

    PROJECTS = load_projects()

    # --- Existing projects ---
    if PROJECTS:
        for name, mods in PROJECTS.items():
            with st.container(border=True):
                st.subheader(name)
                st.write(f"Modules: {len(mods)}")
    else:
        st.info("No projects available.")

    st.write("")

    # --- Upload ZIP ---
    with st.expander("Upload Project ZIP"):
        uploaded_zip = st.file_uploader("Choose a ZIP file", type=["zip"])

        if uploaded_zip is not None:
            os.makedirs("uploaded_projects", exist_ok=True)
            zip_path = os.path.join("uploaded_projects", uploaded_zip.name)

            with open(zip_path, "wb") as f:
                f.write(uploaded_zip.getbuffer())

            extract_folder = os.path.join(
                "uploaded_projects", uploaded_zip.name.replace(".zip", "")
            )
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(extract_folder)

            modules = scan_project(extract_folder)
            st.write("Scanner Output:")
            st.write(modules)

            project_name = uploaded_zip.name.replace(".zip", "")
            projects = load_projects()
            if project_name not in projects:
                create_project(project_name)

            for module in modules.keys():
                add_module(project_name, module)

            for module, deps in modules.items():
                for dep in deps:
                    add_dependency(project_name, module, dep)

            st.success(f"{project_name} imported successfully!")
            st.subheader("Detected Modules & Dependencies")
            for module, deps in modules.items():
                st.write(f"{module} → {deps}")

            st.rerun()

    # --- Create project ---
    with st.expander("Register New Project"):
        project_name = st.text_input("Project Name")
        if st.button("Create Project"):
            if project_name.strip():
                create_project(project_name)
                st.success("Project Created")
                st.rerun()
            else:
                st.error("Enter a project name")

    # --- Add module ---
    with st.expander("Add Module"):
        projects = load_projects()
        if projects:
            selected_project = st.selectbox(
                "Project", list(projects.keys()), key="module_project"
            )
            module_name = st.text_input("Module Name", key="module_name")
            if st.button("Add Module"):
                if module_name.strip():
                    add_module(selected_project, module_name)
                    st.success("Module Added")
                    st.rerun()
                else:
                    st.error("Enter module name")
        else:
            st.warning("Create a project first")

    # --- Add dependency ---
    with st.expander("Add Dependency"):
        projects = load_projects()
        if projects:
            selected_project = st.selectbox(
                "Select Project", list(projects.keys()), key="dependency_project"
            )
            modules = list(projects[selected_project].keys())

            if len(modules) >= 2:
                source_module = st.selectbox("Source Module", modules, key="source_module")
                target_module = st.selectbox("Target Module", modules, key="target_module")
                if st.button("Add Dependency"):
                    if source_module != target_module:
                        add_dependency(selected_project, source_module, target_module)
                        st.success("Dependency Added")
                        st.rerun()
                    else:
                        st.error("Source and Target cannot be the same")
            else:
                st.warning("Add at least 2 modules first")
        else:
            st.warning("Create a project first")

# ===========================================================================
# REPORTS
# ===========================================================================
elif page == "Reports":
    st.markdown(
        f"<div style='font-size:30px;font-weight:700;color:{TEXT};'>Reports</div>"
        f"<div style='color:{MUTED};font-size:14px;margin-bottom:16px;'>"
        "Generated impact analysis reports.</div>",
        unsafe_allow_html=True,
    )

    if "report" not in st.session_state:
        with st.container(border=True):
            st.info("Run an impact analysis from the Dashboard first.")
    else:
        report = st.session_state.report

        with st.container(border=True):
            st.subheader("Impact Analysis Report")
            st.write(f"**Project:** {report['project']}")
            st.write(f"**Generated At:** {report['generated_at']}")
            st.write(f"**Changed Module:** {report['changed_module']}")
            st.write(f"**Risk Level:** {report['risk']}")

            st.divider()
            st.markdown("### Directly Affected Modules")
            if report["direct"]:
                for module in report["direct"]:
                    st.write(f"• {module}")
            else:
                st.write("No direct dependencies affected.")

            st.divider()
            st.markdown("### Indirectly Affected Modules")
            if report["indirect"]:
                for module in report["indirect"]:
                    st.write(f"• {module}")
            else:
                st.write("No indirect dependencies affected.")

            st.divider()
            st.write(f"**Total Impacted Modules:** {report['total_impacted']}")

            if report["total_impacted"] == 0:
                st.info(
                    f"No dependencies found — nothing depends on "
                    f"**{report['changed_module']}**, so this change has no "
                    "downstream impact and is safe to ship. This is also "
                    "noted in the downloaded PDF report."
                )

            if report["risk"] == "HIGH":
                recommendation = "Full regression testing is recommended."
            elif report["risk"] == "MEDIUM":
                recommendation = "Targeted regression testing is recommended."
            else:
                recommendation = "Minimal testing is sufficient."

            st.markdown("### Recommendation")
            st.success(recommendation)

            st.divider()

            # Build the rich, chart-embedded PDF. Generated on demand so a
            # broken report never blocks the rest of the page from rendering.
            try:
                pdf_bytes = build_pdf_report(report)
                safe_name = (
                    f"impact_report_{report['project']}_"
                    f"{report['changed_module']}.pdf"
                    .replace(" ", "_")
                )
                st.download_button(
                    label="⬇  Download PDF report",
                    data=pdf_bytes,
                    file_name=safe_name,
                    mime="application/pdf",
                    type="primary",
                )
            except Exception as exc:  # pragma: no cover - defensive UI guard
                st.error(f"Could not generate the PDF report: {exc}")
