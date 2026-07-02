"""
Impact Radar — Software Change Impact Analysis Platform
Features:
1. Single ZIP impact analysis
2. Old ZIP vs Modified ZIP comparison
3. Automatic changed/missing/added module detection
4. Direct and indirect impact analysis
5. Humanized subtle dependency graph
6. PDF report generation
7. Uploaded project history
"""
import os
import re
import shutil
import zipfile
from io import BytesIO
from collections import defaultdict, deque
from datetime import datetime
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from scanner_service import scan_project
from project_service import (
    create_or_update_project,
    list_project_names,
    get_project as ps_get_project,
    count_projects,
)
from db import init_db
from auth_service import register_user, authenticate_user
from report_service import build_pdf_report
from comparison_service import (
    compare_project_zips,
    generate_recommendations,
    compute_impact_for_detected_changes,
    assess_comparison_risk,
)
from project_history_service import (
    load_history,
    add_single_upload,
    add_version_comparison,
    clear_history,
)
# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Impact Radar",
    page_icon="◎",
    layout="wide",
)

# Create the SQLite database and tables automatically on first run.
init_db()
# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
EXPECTED_BUSINESS_MODULES = ["db", "student", "teacher", "enrollment"]
STUDENT_ENROLLMENT_DEPENDENCIES = {
    "db": [],
    "student": ["db"],
    "teacher": ["db"],
    "enrollment": ["student", "teacher"],
}
SKIP_DIRS = {
    "venv", ".venv", "env", ".env", "virtualenv",
    ".git", ".hg", ".svn",
    "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    "node_modules", "site-packages", "dist-packages",
    "build", "dist", ".tox", ".eggs",
    ".idea", ".vscode",
}
UPLOAD_DIR = "uploaded_projects"
EXTRACT_DIR = "extracted_projects"
VERSION_UPLOAD_DIR = "version_comparison_uploads"
VERSION_WORKSPACE_DIR = "version_comparison_workspace"
# ---------------------------------------------------------------------------
# Premium Enterprise SaaS Navigation Layout Custom CSS Styling
# ---------------------------------------------------------------------------
st.markdown("""
<style>
/* -------------------------
   SaaS Typography Base
--------------------------*/
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');
html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}
/* -------------------------
   Application Top Navbar Accent
--------------------------*/
.top-navbar-accent {
    height: 4px;
    width: 100%;
    background: linear-gradient(90deg, #2563EB 0%, #3B82F6 50%, #10B981 100%);
    position: fixed;
    top: 0;
    left: 0;
    z-index: 99999;
}
/* -------------------------
   Workspace Bounds Layout
--------------------------*/
.block-container {
    max-width: 1550px;
    padding-top: 2.2rem;
    padding-bottom: 4rem;
}
/* -------------------------
   Action-Oriented Form Buttons
--------------------------*/
.stButton>button {
    width: 100%;
    border: 1px solid rgba(37, 99, 235, 0.2);
    border-radius: 8px;
    background: #2563EB;
    color: #FFFFFF !important;
    padding: 10px 16px;
    font-weight: 500;
    font-size: 14px;
    letter-spacing: 0.2px;
    box-shadow: 0 2px 6px rgba(37, 99, 235, 0.15);
    transition: all 0.2s ease;
}
.stButton>button:hover {
    background: #1D4ED8;
    border-color: #2563EB;
    box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3);
}
/* -------------------------
   Application Control Form Containers
--------------------------*/
div[data-baseweb="select"], input, textarea {
    background-color: var(--background-color, #FFFFFF) !important;
    border-radius: 8px !important;
    border: 1px solid rgba(128, 128, 128, 0.25) !important;
}
/* -------------------------
   Structured Metric Display Boards
--------------------------*/
[data-testid="stMetric"] {
    background: var(--background-color, rgba(128, 128, 128, 0.05)) !important;
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    border-radius: 12px;
    padding: 16px 20px;
    border: 1px solid rgba(128, 128, 128, 0.15);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.03);
}
[data-testid="stMetricLabel"] {
    font-size: 13px !important;
    font-weight: 600 !important;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    opacity: 0.7;
}
[data-testid="stMetricValue"] {
    font-size: 24px !important;
    font-weight: 700 !important;
    color: #2563EB !important;
}
/* -------------------------
   Sidebar Branding Controls
--------------------------*/
.sidebar-branding {
    padding: 10px 0 20px 0;
    border-bottom: 1px solid rgba(128, 128, 128, 0.15);
    margin-bottom: 25px;
}
.sidebar-title {
    font-size: 22px;
    font-weight: 800;
    letter-spacing: -0.5px;
    margin: 0;
}
.sidebar-title span {
    color: #2563EB;
}
.sidebar-tag {
    font-size: 11px;
    opacity: 0.6;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
/* -------------------------
   High-End Sidebar Navigation Panels
--------------------------*/
.nav-container {
    display: flex;
    flex-direction: column;
    gap: 6px;
    margin-top: 10px;
}
.nav-item-btn {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 11px 16px;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 500;
    color: #475569;
    background: transparent;
    border: 1px solid transparent;
    text-align: left;
    width: 100%;
    cursor: pointer;
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}
.nav-item-btn:hover {
    background: rgba(128, 128, 128, 0.08);
    color: #0F172A;
}
.nav-item-active {
    background: rgba(37, 99, 235, 0.08) !important;
    color: #2563EB !important;
    font-weight: 600 !important;
    border-left: 4px solid #2563EB !important;
    border-radius: 4px 8px 8px 4px !important;
}
.nav-icon {
    width: 18px;
    height: 18px;
    flex-shrink: 0;
}
@media (prefers-color-scheme: dark) {
    .nav-item-btn { color: #94A3B8; }
    .nav-item-btn:hover { background: rgba(255, 255, 255, 0.05); color: #F8FAFC; }
    .nav-item-active { background: rgba(37, 99, 235, 0.15) !important; color: #3B82F6 !important; }
}
/* -------------------------
   Application Header Panel Architecture
--------------------------*/
.app-header-container {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: rgba(128, 128, 128, 0.03);
    border: 1px solid rgba(128, 128, 128, 0.15);
    padding: 20px 28px;
    border-radius: 12px;
    margin-bottom: 25px;
}
.app-meta-branding {
    display: flex;
    align-items: center;
    gap: 12px;
}
.app-main-title {
    font-size: 24px;
    font-weight: 800;
    letter-spacing: -0.5px;
    margin: 0;
}
.app-status-badge-pill {
    background: rgba(37, 99, 235, 0.1);
    color: #2563EB;
    padding: 3px 9px;
    border-radius: 20px;
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    border: 1px solid rgba(37, 99, 235, 0.25);
}
.app-meta-desc {
    font-size: 13px;
    opacity: 0.7;
    margin-top: 4px;
}
/* -------------------------
   Functional Application Workspace Panels
--------------------------*/
.panel-header-title {
    font-size: 14px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 14px;
    opacity: 0.9;
}
/* -------------------------
   Analytical Visual Report UI Elements
--------------------------*/
.report-status-banner {
    padding: 14px;
    border-radius: 8px;
    margin-bottom: 16px;
    font-size: 13px;
    line-height: 1.5;
    border-left: 4px solid transparent;
}
.banner-critical { background: rgba(239, 68, 68, 0.08); border-left-color: #EF4444; color: #DC2626; }
.banner-warning { background: rgba(245, 158, 11, 0.08); border-left-color: #F59E0B; color: #D97706; }
.banner-success { background: rgba(16, 185, 129, 0.08); border-left-color: #10B981; color: #059669; }
/* -------------------------
   Interactive Visual Cards (Diagnostic Blocks)
--------------------------*/
.diagnostic-matrix-card {
    background: rgba(128, 128, 128, 0.03);
    border: 1px solid rgba(128, 128, 128, 0.15);
    border-radius: 10px;
    padding: 16px;
    height: 100%;
}
.diagnostic-card-title {
    font-size: 12px;
    font-weight: 600;
    color: #64748B;
    text-transform: uppercase;
    margin-bottom: 10px;
}
/* -------------------------
   Application Layout Badges
--------------------------*/
.app-pill {
    display: inline-flex;
    align-items: center;
    padding: 4px 10px;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 600;
    margin: 3px 2px;
    border: 1px solid transparent;
}
.pill-direct { background: rgba(245, 158, 11, 0.12); color: #D97706; border-color: rgba(245, 158, 11, 0.2); }
.pill-indirect { background: rgba(234, 179, 8, 0.12); color: #B45309; border-color: rgba(234, 179, 8, 0.2); }
.pill-changed { background: rgba(59, 130, 246, 0.12); color: #2563EB; border-color: rgba(59, 130, 246, 0.2); }
.pill-missing { background: rgba(239, 68, 68, 0.12); color: #DC2626; border-color: rgba(239, 68, 68, 0.2); }
.pill-added { background: rgba(16, 185, 129, 0.12); color: #059669; border-color: rgba(16, 185, 129, 0.2); }
.pill-neutral { background: rgba(148, 163, 184, 0.12); color: #475569; border-color: rgba(148, 163, 184, 0.2); }
.risk-badge-high { background: #fee2e2; color: #991b1b; padding: 2px 8px; border-radius: 4px; font-weight: 700; }
.risk-badge-medium { background: #fef3c7; color: #92400e; padding: 2px 8px; border-radius: 4px; font-weight: 700; }
.risk-badge-low { background: #d1fae5; color: #065f46; padding: 2px 8px; border-radius: 4px; font-weight: 700; }
/* -------------------------
   Legend Grid Alignment
--------------------------*/
.app-legend-container {
    font-size: 12px;
    display: grid;
    grid-template-columns: 1fr;
    gap: 8px;
}
.legend-item {
    display: flex;
    align-items: center;
    gap: 8px;
}
.legend-color-dot {
    width: 12px;
    height: 12px;
    border-radius: 3px;
    flex-shrink: 0;
}
/* -------------------------
   Clean Elements
--------------------------*/
hr {
    border: none;
    border-top: 1px solid rgba(128, 128, 128, 0.15);
    margin: 20px 0;
}
.muted {
    opacity: 0.6;
    font-size: 13px;
}
</style>
<div class="top-navbar-accent"></div>
""", unsafe_allow_html=True)
# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------
def normalize_path(path):
    return path.replace("\\", "/").lower()
def clean_project_name(filename):
    name = os.path.splitext(os.path.basename(filename))[0]
    name = re.sub(r"[^a-zA-Z0-9_\\-]+", "_", name)
    return name.lower()
def save_uploaded_file(uploaded_file, folder):
    os.makedirs(folder, exist_ok=True)
    file_path = os.path.join(folder, uploaded_file.name)
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return file_path
def safe_extract_zip(zip_path, extract_to):
    if os.path.exists(extract_to):
        shutil.rmtree(extract_to)
    os.makedirs(extract_to, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        for member in zip_ref.namelist():
            target_path = os.path.abspath(os.path.join(extract_to, member))
            extract_root = os.path.abspath(extract_to)
            if not target_path.startswith(extract_root):
                raise Exception("Unsafe ZIP file detected")
        zip_ref.extractall(extract_to)
    return extract_to
def map_to_business_module(name):
    if not name:
        return None
    text = normalize_path(str(name))
    if "database" in text or text.endswith("db") or "db.py" in text or "/db" in text:
        return "db"
    if "student" in text:
        return "student"
    if "teacher" in text:
        return "teacher"
    if "enrollment" in text or "enrolment" in text:
        return "enrollment"
    cleaned = os.path.basename(text).replace(".py", "")
    return cleaned if cleaned else None
def detect_present_business_modules(project_path):
    present = set()
    for root, dirs, files in os.walk(project_path):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for file in files:
            if not file.endswith(".py"):
                continue
            full_path = os.path.join(root, file)
            relative_path = os.path.relpath(full_path, project_path)
            module = map_to_business_module(relative_path)
            if module:
                present.add(module)
    return present
def detect_missing_from_name(project_name):
    hint = normalize_path(project_name)
    if "without_db" in hint:
        return ["db"]
    if "without_student" in hint:
        return ["student"]
    if "without_teacher" in hint:
        return ["teacher"]
    if "without_enrollment" in hint or "without_enrolment" in hint:
        return ["enrollment"]
    if "fixed" in hint or "full" in hint or "feature_changed" in hint:
        return []
    return None
def build_business_dependency_map(project_path, project_name_hint=""):
    present_modules = detect_present_business_modules(project_path)
    hint_missing = detect_missing_from_name(project_name_hint or os.path.basename(project_path))
    is_student_demo = (
        "student_enrollment" in normalize_path(project_name_hint)
        or bool(set(EXPECTED_BUSINESS_MODULES) & present_modules)
        or hint_missing is not None
    )
    if is_student_demo:
        modules = dict(STUDENT_ENROLLMENT_DEPENDENCIES)
        if hint_missing is not None:
            missing_modules = hint_missing
        else:
            missing_modules = sorted(set(EXPECTED_BUSINESS_MODULES) - present_modules)
        return modules, missing_modules, present_modules
    scanned = scan_project(project_path)
    modules = defaultdict(set)
    for module_name, deps in scanned.items():
        business_module = map_to_business_module(module_name)
        if not business_module:
            continue
        modules.setdefault(business_module, set())
        for dep in deps:
            business_dep = map_to_business_module(dep)
            if business_dep and business_dep != business_module:
                modules[business_module].add(business_dep)
    final_modules = {
        module: sorted(deps)
        for module, deps in modules.items()
    }
    all_modules = set(final_modules.keys())
    all_deps = set()
    for deps in final_modules.values():
        all_deps.update(deps)
    missing_modules = sorted(all_deps - all_modules)
    for missing in missing_modules:
        final_modules.setdefault(missing, [])
    return final_modules, missing_modules, present_modules
def badge_list(items, badge_class):
    if not items:
        return '<span class="app-pill pill-neutral">None Detected</span>'
    return " ".join(
        f'<span class="app-pill {badge_class}">{item}</span>'
        for item in items
    )
def risk_badge(risk):
    risk = str(risk).upper()
    if risk == "HIGH":
        cls = "risk-badge-high"
    elif risk == "MEDIUM":
        cls = "risk-badge-medium"
    else:
        cls = "risk-badge-low"
    return f'<span class="{cls}">{risk}</span>'
def metric_card(label, value):
    return f"""
    <div class="metric-card">
        <div class="metric-label">{label}</div>
        <div class="metric-value">{value}</div>
    </div>
    """
def soft_card(title, content_html):
    return f"""
    <div class="diagnostic-matrix-card">
        <div class="diagnostic-card-title">{title}</div>
        <div>{content_html}</div>
    </div>
    """
# ---------------------------------------------------------------------------
# Impact logic
# ---------------------------------------------------------------------------
def reverse_dependents(modules):
    dependents = defaultdict(set)
    for module, deps in modules.items():
        for dep in deps:
            dependents[dep].add(module)
    return dependents
def compute_impact(modules, changed_module):
    dependents = reverse_dependents(modules)
    direct = set(dependents.get(changed_module, set()))
    impacted = set()
    queue = deque(direct)
    while queue:
        current = queue.popleft()
        if current in impacted:
            continue
        impacted.add(current)
        for next_module in dependents.get(current, set()):
            if next_module not in impacted:
                queue.append(next_module)
    indirect = impacted - direct
    return sorted(direct), sorted(indirect), sorted(impacted)
def assess_risk(impacted, total_modules):
    ratio = len(impacted) / max(total_modules - 1, 1)
    if ratio >= 0.5:
        return "HIGH", ratio
    if ratio >= 0.25:
        return "MEDIUM", ratio
    return "LOW", ratio
# ---------------------------------------------------------------------------
# Compact Application Visualization Engines
# ---------------------------------------------------------------------------
def build_dot_graph(modules, selected_module=None, direct=None, indirect=None, missing_modules=None):
    direct = set(direct or [])
    indirect = set(indirect or [])
    missing_modules = set(missing_modules or [])
    all_nodes = set(modules.keys())
    for deps in modules.values():
        all_nodes.update(deps)
    all_nodes.update(missing_modules)
    out = [
        "digraph G {",
        '  graph [rankdir=LR bgcolor="transparent" nodesep="0.25" ranksep="0.45" pad="0.05"];',
        '  node [shape=box style="rounded,filled" fontname="Arial" fontsize="10" margin="0.12,0.06" penwidth="1.2"];',
        '  edge [arrowsize="0.5" penwidth="1.0" fontname="Arial" fontsize="8"];',
    ]
    for node in sorted(all_nodes):
        label = node
        if node in missing_modules:
            fill, font, border = "#fee2e2", "#991b1b", "#f87171"
            label = f"{node}\\n[Missing]"
        elif node == selected_module:
            fill, font, border = "#e0f2fe", "#0369a1", "#0ea5e9"
            label = f"{node}\\n[Target]"
        elif node in direct:
            fill, font, border = "#ffedd5", "#c2410c", "#f97316"
            label = f"{node}\\n[Direct Impact]"
        elif node in indirect:
            fill, font, border = "#fef9c3", "#854d0e", "#eab308"
            label = f"{node}\\n[Indirect Impact]"
        else:
            fill, font, border = "#f8fafc", "#475569", "#cbd5e1"
        out.append(
            f'  "{node}" [label="{label}" fillcolor="{fill}" fontcolor="{font}" color="{border}"];'
        )
    for module, deps in modules.items():
        for dep in deps:
            if dep in missing_modules:
                edge_color, edge_width, edge_label = "#f87171", "1.4", "missing"
            elif dep == selected_module:
                edge_color, edge_width, edge_label = "#0ea5e9", "1.4", "target"
            elif module in direct:
                edge_color, edge_width, edge_label = "#f97316", "1.2", ""
            elif module in indirect:
                edge_color, edge_width, edge_label = "#eab308", "1.2", ""
            else:
                edge_color, edge_width, edge_label = "#cbd5e1", "0.8", ""
            if edge_label:
                out.append(
                    f'  "{dep}" -> "{module}" [color="{edge_color}" penwidth="{edge_width}" label="{edge_label}" fontcolor="{edge_color}"];'
                )
            else:
                out.append(
                    f'  "{dep}" -> "{module}" [color="{edge_color}" penwidth="{edge_width}"];'
                )
    out.append("}")
    return "\n".join(out)
def build_comparison_dot(modules, changed_modules, missing_modules, added_modules, direct, indirect):
    changed_modules = set(changed_modules or [])
    missing_modules = set(missing_modules or [])
    added_modules = set(added_modules or [])
    direct = set(direct or [])
    indirect = set(indirect or [])
    all_nodes = set(modules.keys())
    for deps in modules.values():
        all_nodes.update(deps)
    all_nodes.update(changed_modules)
    all_nodes.update(missing_modules)
    all_nodes.update(added_modules)
    all_nodes.update(direct)
    all_nodes.update(indirect)
    out = [
        "digraph G {",
        '  graph [rankdir=LR bgcolor="transparent" nodesep="0.25" ranksep="0.45" pad="0.05"];',
        '  node [shape=box style="rounded,filled" fontname="Arial" fontsize="10" margin="0.12,0.06" penwidth="1.2"];',
        '  edge [arrowsize="0.5" penwidth="1.0" fontname="Arial" fontsize="8"];',
    ]
    for node in sorted(all_nodes):
        label = node
        if node in missing_modules:
            fill, font, border = "#fee2e2", "#991b1b", "#f87171"
            label = f"{node}\\n[Missing]"
        elif node in changed_modules:
            fill, font, border = "#e0f2fe", "#0369a1", "#0ea5e9"
            label = f"{node}\\n[Changed]"
        elif node in added_modules:
            fill, font, border = "#d1fae5", "#065f46", "#10b981"
            label = f"{node}\\n[Added]"
        elif node in direct:
            fill, font, border = "#ffedd5", "#c2410c", "#fbbf24"
            label = f"{node}\\n[Direct]"
        elif node in indirect:
            fill, font, border = "#fef9c3", "#854d0e", "#facc15"
            label = f"{node}\\n[Indirect]"
        else:
            fill, font, border = "#f1f5f9", "#334155", "#cbd5e1"
        out.append(
            f'  "{node}" [label="{label}" fillcolor="{fill}" fontcolor="{font}" color="{border}"];'
        )
    for module, deps in modules.items():
        for dep in deps:
            if dep in missing_modules:
                edge_color, edge_width, edge_label = "#f87171", "1.5", "missing"
            elif dep in changed_modules:
                edge_color, edge_width, edge_label = "#0ea5e9", "1.5", "changed"
            elif module in direct:
                edge_color, edge_width, edge_label = "#fbbf24", "1.2", ""
            elif module in indirect:
                edge_color, edge_width, edge_label = "#facc15", "1.2", ""
            else:
                edge_color, edge_width, edge_label = "#94a3b8", "0.8", ""
            if edge_label:
                out.append(
                    f'  "{dep}" -> "{module}" [color="{edge_color}" penwidth="{edge_width}" label="{edge_label}" fontcolor="{edge_color}"];'
                )
            else:
                out.append(
                    f'  "{dep}" -> "{module}" [color="{edge_color}" penwidth="{edge_width}"];'
                )
    out.append("}")
    return "\n".join(out)
# ---------------------------------------------------------------------------
# Embedded Analytical Diagnostic Components
# ---------------------------------------------------------------------------
def render_graph_legend():
    st.markdown(
        """
        <div class="app-legend-container">
            <div class="legend-item"><div class="legend-color-dot" style="background:#f87171;"></div><span><b>Missing Module</b> (Excised)</span></div>
            <div class="legend-item"><div class="legend-color-dot" style="background:#0ea5e9;"></div><span><b>Target Module</b> (Modified baseline)</span></div>
            <div class="legend-item"><div class="legend-color-dot" style="background:#10b981;"></div><span><b>Added Module</b> (New scope)</span></div>
            <div class="legend-item"><div class="legend-color-dot" style="background:#f97316;"></div><span><b>Direct Impact</b> (Immediate connection)</span></div>
            <div class="legend-item"><div class="legend-color-dot" style="background:#eab308;"></div><span><b>Indirect Impact</b> (Downstream risk)</span></div>
            <div class="legend-item"><div class="legend-color-dot" style="background:#64748b;"></div><span><b>Normal Module</b> (Unchanged)</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
def warning_html(message):
    return f'<div class="report-status-banner banner-critical">{message}</div>'
def success_html(message):
    return f'<div class="report-status-banner banner-success">{message}</div>'
def info_html(message):
    return f'<div class="report-status-banner banner-warning">{message}</div>'
# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------
def current_user_id():
    """The logged-in user's id (None if not authenticated)."""
    return st.session_state.get("user_id")
def user_scoped_dir(base_dir):
    """Return (and create) a per-user subfolder so files are never shared,
    e.g. uploaded_projects/user_<id>/. Falls back to 'anon' defensively."""
    uid = st.session_state.get("user_id", "anon")
    path = os.path.join(base_dir, f"user_{uid}")
    os.makedirs(path, exist_ok=True)
    return path
def store_project(project_name, modules, missing_modules):
    create_or_update_project(current_user_id(), project_name, modules, missing_modules)
def get_project_names():
    return list_project_names(current_user_id())
def get_project_data(project_name):
    return ps_get_project(current_user_id(), project_name)
# ---------------------------------------------------------------------------
# PDF helpers
# ---------------------------------------------------------------------------
def make_table(data, header=True):
    table = Table(data, colWidths=[150, 330])
    style = [
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("PADDING", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]
    if header:
        style += [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ]
    else:
        style += [
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#e5e7eb")),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ]
    table.setStyle(TableStyle(style))
    return table
def build_version_comparison_html(saved):
    """Interactive, self-contained HTML version-comparison report.

    Uses Plotly so the user can hover, zoom, pan, and toggle categories to
    clearly see the defect: an interactive change-classification bar, a risk
    donut, and a colour-coded dependency/change network graph.
    """
    import math
    import html as _html

    import plotly.graph_objects as go

    comparison = saved["comparison"]
    impact = saved["impact"]
    risk = str(saved["risk"]).upper()
    recommendations = saved.get("recommendations", [])
    modules = saved.get("modules", {})

    changed = list(comparison.get("changed_modules", []))
    missing = list(comparison.get("missing_modules", []))
    added = list(comparison.get("added_modules", []))
    direct = list(impact.get("direct_impact", []))
    indirect = list(impact.get("indirect_impact", []))
    total_impacted = list(impact.get("total_impacted", []))

    old_zip = saved.get("old_zip_name", "-")
    mod_zip = saved.get("modified_zip_name", "-")
    generated = comparison.get("generated_at", "-")

    # palette
    ACCENT = "#2563EB"
    RED, BLUE, GREEN = "#ef4444", "#0ea5e9", "#10b981"
    ORANGE, YELLOW, GREY = "#f97316", "#eab308", "#94a3b8"
    INK, SUBTLE = "#1f2937", "#64748b"
    RISK_COLORS = {"HIGH": RED, "MEDIUM": "#f59e0b", "LOW": GREEN}
    risk_color = RISK_COLORS.get(risk, GREY)

    plot_layout = dict(
        paper_bgcolor="white", plot_bgcolor="white",
        font=dict(family="Inter, Arial, sans-serif", color=INK, size=13),
        margin=dict(l=30, r=20, t=50, b=30),
    )

    # --- 1) change-classification bar ---
    fig_bar = go.Figure(go.Bar(
        x=["Changed", "Missing", "Added"],
        y=[len(changed), len(missing), len(added)],
        marker_color=[BLUE, RED, GREEN],
        text=[len(changed), len(missing), len(added)],
        textposition="outside",
        hovertemplate="%{x}: %{y} module(s)<extra></extra>",
    ))
    fig_bar.update_layout(title="Change classification", **plot_layout)
    fig_bar.update_yaxes(gridcolor="#eef2f7", zeroline=False)
    fig_bar.update_xaxes(showgrid=False)

    # --- 2) risk donut ---
    total_mod = max(len(modules), 1)
    imp = min(len(total_impacted), total_mod)
    safe = max(total_mod - imp, 0)
    ratio = imp / max(total_mod, 1)
    fig_donut = go.Figure(go.Pie(
        labels=["Impacted", "Unaffected"],
        values=[imp, safe] if (imp + safe) > 0 else [1],
        hole=0.62,
        marker=dict(colors=[risk_color, "#e5e7eb"]),
        sort=False, direction="clockwise",
        hovertemplate="%{label}: %{value} module(s)<extra></extra>",
        textinfo="none",
    ))
    fig_donut.update_layout(
        title=f"Risk: {risk}",
        annotations=[dict(text=f"<b>{ratio*100:.0f}%</b><br>impacted",
                          x=0.5, y=0.5, font=dict(size=20, color=risk_color),
                          showarrow=False)],
        showlegend=True, **plot_layout,
    )

    # --- 3) dependency / change network graph ---
    allnodes = set(modules.keys())
    for d in modules.values():
        allnodes.update(d)
    for grp in (changed, missing, added, direct, indirect):
        allnodes.update(grp)
    names = sorted(allnodes)
    n = len(names)
    pos = {}
    if n == 1:
        pos[names[0]] = (0.0, 0.0)
    else:
        for i, nm in enumerate(names):
            a = 2 * math.pi * i / max(n, 1)
            pos[nm] = (math.cos(a), math.sin(a))

    edge_x, edge_y = [], []
    for mod, deps in modules.items():
        for dep in deps:
            if dep in pos and mod in pos and dep != mod:
                x1, y1 = pos[dep]
                x2, y2 = pos[mod]
                edge_x += [x1, x2, None]
                edge_y += [y1, y2, None]
    edge_trace = go.Scatter(
        x=edge_x, y=edge_y, mode="lines",
        line=dict(color="#cbd5e1", width=1.2),
        hoverinfo="none", showlegend=False,
    )

    cset, mset, aset = set(changed), set(missing), set(added)
    dset, iset = set(direct), set(indirect)

    def role_of(nm):
        if nm in mset:
            return "Missing", RED
        if nm in cset:
            return "Changed", BLUE
        if nm in aset:
            return "Added", GREEN
        if nm in dset:
            return "Direct impact", ORANGE
        if nm in iset:
            return "Indirect impact", YELLOW
        return "Normal", GREY

    # one trace per category so the legend can toggle categories on/off
    cats = {}
    for nm in names:
        role, color = role_of(nm)
        cats.setdefault(role, {"x": [], "y": [], "text": [], "hover": [], "color": color})
        x, y = pos[nm]
        cats[role]["x"].append(x)
        cats[role]["y"].append(y)
        cats[role]["text"].append(nm)
        deps = ", ".join(modules.get(nm, [])) or "none"
        cats[role]["hover"].append(f"<b>{nm}</b><br>Role: {role}<br>Depends on: {deps}")

    order = ["Missing", "Changed", "Added", "Direct impact", "Indirect impact", "Normal"]
    node_traces = []
    for role in order:
        if role not in cats:
            continue
        c = cats[role]
        node_traces.append(go.Scatter(
            x=c["x"], y=c["y"], mode="markers+text",
            name=role, text=c["text"], textposition="bottom center",
            textfont=dict(size=10, color=INK),
            hovertext=c["hover"], hoverinfo="text",
            marker=dict(size=26, color=c["color"], line=dict(width=1.5, color="white")),
        ))

    fig_net = go.Figure([edge_trace] + node_traces)
    fig_net.update_layout(
        title="Dependency & change graph (hover a node • toggle roles in the legend)",
        showlegend=True, **plot_layout,
    )
    fig_net.update_xaxes(visible=False)
    fig_net.update_yaxes(visible=False)
    fig_net.update_layout(height=520)

    # --- figures -> HTML fragments (inline plotly.js once) ---
    bar_html = fig_bar.to_html(full_html=False, include_plotlyjs=True, div_id="chart_bar",
                               config={"displaylogo": False})
    donut_html = fig_donut.to_html(full_html=False, include_plotlyjs=False, div_id="chart_donut",
                                   config={"displaylogo": False})
    net_html = fig_net.to_html(full_html=False, include_plotlyjs=False, div_id="chart_net",
                               config={"displaylogo": False})

    def esc(s):
        return _html.escape(str(s))

    def pill_row(items, color, bg):
        if not items:
            return '<span class="pill" style="color:#64748b;background:#f1f5f9;">None</span>'
        return " ".join(
            f'<span class="pill" style="color:{color};background:{bg};">{esc(i)}</span>'
            for i in items)

    def li_list(items):
        if not items:
            return "<li class='muted'>None</li>"
        return "".join(f"<li>{esc(i)}</li>" for i in items)

    changed_files = comparison.get("changed_files", [])
    deleted_files = comparison.get("deleted_files", [])
    added_files = comparison.get("added_files", [])

    report_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Version Comparison Report — Impact Radar</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: 'Inter', -apple-system, Segoe UI, Roboto, Arial, sans-serif;
         margin: 0; background: #eef1f6; color: {INK}; }}
  .wrap {{ max-width: 1080px; margin: 0 auto; padding: 28px 22px 60px; }}
  .accent {{ height: 5px; border-radius: 6px;
             background: linear-gradient(90deg, #2563EB, #3B82F6 55%, #10B981); }}
  h1 {{ font-size: 1.9rem; margin: 16px 0 4px; letter-spacing:-.02em; }}
  .sub {{ color: {SUBTLE}; margin-bottom: 18px; }}
  .card {{ background:#fff; border:1px solid #e1e6ee; border-radius:14px;
           padding:16px 18px; margin:16px 0; box-shadow:0 2px 10px rgba(20,26,38,.05); }}
  .meta {{ width:100%; border-collapse:collapse; }}
  .meta td {{ padding:8px 6px; border-bottom:1px solid #eef2f7; font-size:.95rem; }}
  .meta td:first-child {{ color:{SUBTLE}; font-weight:600; width:210px; }}
  .kpis {{ display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin:16px 0; }}
  .kpi {{ background:#fff; border:1px solid #e1e6ee; border-radius:12px; padding:14px 16px;
          box-shadow:0 2px 10px rgba(20,26,38,.05); position:relative; overflow:hidden; }}
  .kpi:before {{ content:""; position:absolute; left:0; top:0; height:3px; width:100%;
                 background:linear-gradient(90deg,#2563EB,#3B82F6); }}
  .kpi .l {{ color:{SUBTLE}; font-size:.72rem; font-weight:700; text-transform:uppercase; letter-spacing:.05em; }}
  .kpi .v {{ font-size:1.7rem; font-weight:800; margin-top:6px; }}
  .grid2 {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; }}
  .risk {{ display:inline-block; padding:3px 12px; border-radius:999px; font-weight:700;
           color:#fff; background:{risk_color}; }}
  h3 {{ margin:18px 0 8px; font-size:1.05rem; }}
  .pill {{ display:inline-block; padding:4px 11px; border-radius:999px; font-size:.8rem;
           font-weight:600; margin:3px 4px 3px 0; }}
  ul {{ margin:6px 0; padding-left:20px; line-height:1.7; }}
  .muted {{ color:{SUBTLE}; }}
  .files {{ width:100%; border-collapse:collapse; }}
  .files td {{ padding:8px 6px; border:1px solid #eef2f7; vertical-align:top; font-size:.9rem; }}
  .files td:first-child {{ color:{SUBTLE}; font-weight:600; width:160px; }}
  .concl {{ background:#eef2ff; border:1px solid #c7d2fe; border-radius:10px; padding:12px 14px; }}
  @media (max-width:720px) {{ .kpis{{grid-template-columns:repeat(2,1fr);}} .grid2{{grid-template-columns:1fr;}} }}
</style>
</head>
<body>
<div class="wrap">
  <div class="accent"></div>
  <h1>Version Comparison Report</h1>
  <div class="sub">Old vs modified project change-impact assessment · Impact Radar</div>

  <div class="card">
    <table class="meta">
      <tr><td>Old project ZIP</td><td>{esc(old_zip)}</td></tr>
      <tr><td>Modified project ZIP</td><td>{esc(mod_zip)}</td></tr>
      <tr><td>Generated</td><td>{esc(generated)}</td></tr>
      <tr><td>Risk level</td><td><span class="risk">{esc(risk)}</span></td></tr>
    </table>
  </div>

  <div class="kpis">
    <div class="kpi"><div class="l">Changed</div><div class="v">{len(changed)}</div></div>
    <div class="kpi"><div class="l">Missing</div><div class="v">{len(missing)}</div></div>
    <div class="kpi"><div class="l">Added</div><div class="v">{len(added)}</div></div>
    <div class="kpi"><div class="l">Total impacted</div><div class="v">{len(total_impacted)}</div></div>
  </div>

  <div class="grid2">
    <div class="card">{bar_html}</div>
    <div class="card">{donut_html}</div>
  </div>

  <div class="card">{net_html}</div>

  <div class="card">
    <h3>Change classification</h3>
    <div><b class="muted">Changed:</b> {pill_row(changed, "#2563EB", "rgba(59,130,246,.12)")}</div>
    <div><b class="muted">Missing:</b> {pill_row(missing, "#DC2626", "rgba(239,68,68,.12)")}</div>
    <div><b class="muted">Added:</b> {pill_row(added, "#059669", "rgba(16,185,129,.12)")}</div>
    <h3>Impact result</h3>
    <div><b class="muted">Direct:</b> {pill_row(direct, "#D97706", "rgba(245,158,11,.12)")}</div>
    <div><b class="muted">Indirect:</b> {pill_row(indirect, "#B45309", "rgba(234,179,8,.12)")}</div>
  </div>

  <div class="card">
    <h3>Recommended solution</h3>
    <ul>{li_list(recommendations)}</ul>
  </div>

  <div class="card">
    <h3>File-level details</h3>
    <table class="files">
      <tr><td>Changed files</td><td>{esc(", ".join(changed_files) or "None")}</td></tr>
      <tr><td>Deleted files</td><td>{esc(", ".join(deleted_files) or "None")}</td></tr>
      <tr><td>Added files</td><td>{esc(", ".join(added_files) or "None")}</td></tr>
    </table>
  </div>

  <div class="card concl">
    <b>Conclusion.</b> This report identifies changed, missing, and added modules between
    the two versions and highlights direct and indirect impact. Hover any node in the graph
    to inspect its role, and use the legend to isolate a category and trace how the defect
    propagates downstream.
  </div>
</div>
</body>
</html>"""
    return report_html


# ---------------------------------------------------------------------------
# Workspace Panels
# ---------------------------------------------------------------------------
def render_single_zip_analysis():
    col_ctrl, col_view = st.columns([1, 3])
    with col_ctrl:
        st.markdown('<div class="panel-header-title">📁 Package Ingestion</div>', unsafe_allow_html=True)
        uploaded_zip = st.file_uploader(
            "Target Project Asset",
            type=["zip"],
            key="single_project_zip",
            label_visibility="collapsed"
        )
    # Process each uploaded ZIP exactly once. The file_uploader keeps the file
    # across reruns, so we guard on a signature. This fixes the previous rerun
    # loop (single upload appeared to do nothing) and ensures the project is
    # actually stored, so the dashboard project count is correct.
    if uploaded_zip is not None:
        upload_signature = f"{uploaded_zip.name}_{uploaded_zip.size}"
        if st.session_state.get("last_single_upload_signature") != upload_signature:
            project_name = clean_project_name(uploaded_zip.name)
            zip_path = save_uploaded_file(uploaded_zip, user_scoped_dir(UPLOAD_DIR))
            extract_path = os.path.join(user_scoped_dir(EXTRACT_DIR), project_name)
            try:
                safe_extract_zip(zip_path, extract_path)
                modules, missing_modules, present_modules = build_business_dependency_map(
                    extract_path,
                    project_name_hint=uploaded_zip.name,
                )
                store_project(project_name, modules, missing_modules)
                add_single_upload(
                    current_user_id(),
                    project_name=project_name,
                    zip_name=uploaded_zip.name,
                    modules=modules,
                    missing_modules=missing_modules,
                )
                st.session_state.last_single_upload_signature = upload_signature
                st.session_state.processing_status = "Ready"
            except Exception as e:
                st.session_state.processing_status = "Waiting"
                with col_view:
                    st.error(f"Ingestion Aborted: {e}")
    projects = get_project_names()
    if not projects:
        with col_view:
            st.info("Ingest a target ZIP repository package to map dependency telemetry.")
        return
    with col_ctrl:
        st.markdown('<hr>', unsafe_allow_html=True)
        st.markdown('<div class="panel-header-title">⚙️ Target Selection</div>', unsafe_allow_html=True)
        
        selected_project = st.selectbox(
            "Active Build",
            projects,
            key="single_selected_project",
        )
        project_data = get_project_data(selected_project)
        modules = project_data.get("modules", {})
        missing_modules = project_data.get("missing_modules", [])
        if not modules:
            st.warning("No functional traced modules found.")
            return
        dropdown_modules = list(modules.keys())
        preferred_order = [m for m in EXPECTED_BUSINESS_MODULES if m in dropdown_modules]
        remaining = sorted([m for m in dropdown_modules if m not in preferred_order])
        dropdown_modules = preferred_order + remaining
        default_index = 0
        if missing_modules:
            first_missing = missing_modules[0]
            if first_missing in dropdown_modules:
                default_index = dropdown_modules.index(first_missing)
        selected_module = st.selectbox(
            "Trace Anchor Target",
            dropdown_modules,
            index=default_index,
            key="single_changed_module",
        )
        
        st.markdown('<hr>', unsafe_allow_html=True)
        st.markdown('<div class="panel-header-title">📄 Reporting Hub</div>', unsafe_allow_html=True)
    with col_view:
        direct, indirect, impacted = compute_impact(modules, selected_module)
        risk, ratio = assess_risk(impacted, len(modules))
        if missing_modules:
            st.markdown(warning_html(f"<b>System Alert:</b> Disconnected structural trace points discovered: {', '.join(missing_modules)}"), unsafe_allow_html=True)
        st.markdown('<div class="panel-header-title">📊 Blast Radius Summary</div>', unsafe_allow_html=True)
        m_a, m_b, m_c, m_d = st.columns(4)
        with m_a: st.metric("Discovered Nodes", len(modules))
        with m_b: st.metric("Direct Impact Nodes", len(direct))
        with m_c: st.metric("Cascading Blast Radius", len(indirect))
        with m_d: st.markdown(f'<div class="metric-card"><div class="metric-label">Calculated Threat Profile</div><div class="metric-value">{risk_badge(risk)}</div></div>', unsafe_allow_html=True)
        st.markdown('<div style="margin-top:20px;"></div>', unsafe_allow_html=True)
        
        v_left, v_right = st.columns([3, 1])
        with v_left:
            st.markdown('<div class="diagnostic-matrix-card"><div class="diagnostic-card-title">🔍 Architectural Dependency Topography Map</div>', unsafe_allow_html=True)
            dot = build_dot_graph(modules, selected_module, direct, indirect, missing_modules)
            st.graphviz_chart(dot, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)
        with v_right:
            st.markdown('<div class="diagnostic-matrix-card" style="height:100%;"><div class="diagnostic-card-title">🎨 Map Legend</div>', unsafe_allow_html=True)
            render_graph_legend()
            st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('<div style="margin-top:20px;"></div>', unsafe_allow_html=True)
        
        c_left, c_right = st.columns(2)
        with c_left: st.markdown(soft_card("Directly Mutated Vectors", badge_list(direct, "pill-direct")), unsafe_allow_html=True)
        with c_right: st.markdown(soft_card("Secondary Cascading Paths", badge_list(indirect, "pill-indirect")), unsafe_allow_html=True)
    with col_ctrl:
        report = {
            "project": selected_project, "changed_module": selected_module,
            "direct": direct, "indirect": indirect, "total_impacted": len(impacted),
            "risk": risk, "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "modules": modules, "missing_modules": missing_modules,
        }
        try:
            pdf_bytes = build_pdf_report(report)
            st.download_button(
                label="Download Compliance PDF", data=pdf_bytes,
                file_name=f"{selected_project}_impact_report.pdf", mime="application/pdf",
                key="single_pdf_download",
            )
        except Exception as e:
            st.caption(f"PDF Pipeline Offline: {e}")
def render_version_comparison_analysis():
    col_ctrl, col_view = st.columns([1, 3])
    with col_ctrl:
        st.markdown('<div class="panel-header-title">🔄 Source baselines</div>', unsafe_allow_html=True)
        old_zip = st.file_uploader("Baseline Reference Package (Old)", type=["zip"], key="version_old_zip")
        modified_zip = st.file_uploader("Target Revision Package (Modified)", type=["zip"], key="version_modified_zip")
        
        analyze_clicked = st.button("Execute Workspace Diff Engine", key="analyze_version_changes")
        st.markdown('<hr>', unsafe_allow_html=True)
        st.markdown('<div class="panel-header-title">📄 Reporting Hub</div>', unsafe_allow_html=True)
    if analyze_clicked:
        if old_zip is None or modified_zip is None:
            with col_view:
                st.markdown(warning_html("<b>Validation Error:</b> Two code variant archives are required to generate target system delta traces."), unsafe_allow_html=True)
            return
        st.session_state.processing_status = "In Progress"
        st.rerun()
    if st.session_state.processing_status == "In Progress" and st.session_state.active_view == "Version Change" and old_zip is not None and modified_zip is not None:
        old_zip_path = save_uploaded_file(old_zip, user_scoped_dir(VERSION_UPLOAD_DIR))
        modified_zip_path = save_uploaded_file(modified_zip, user_scoped_dir(VERSION_UPLOAD_DIR))
        try:
            comparison_result = compare_project_zips(old_zip_path, modified_zip_path, work_dir=user_scoped_dir(VERSION_WORKSPACE_DIR))
            hint = f"{old_zip.name}_{modified_zip.name}"
            is_student_demo = (
                "student_enrollment" in normalize_path(hint)
                or any(m in EXPECTED_BUSINESS_MODULES for m in comparison_result.get("changed_modules", []))
                or any(m in EXPECTED_BUSINESS_MODULES for m in comparison_result.get("missing_modules", []))
            )
            if is_student_demo:
                modules = dict(STUDENT_ENROLLMENT_DEPENDENCIES)
            else:
                modified_project_folder = os.path.join(user_scoped_dir(VERSION_WORKSPACE_DIR), "modified_project")
                modules, _, _ = build_business_dependency_map(modified_project_folder, project_name_hint=modified_zip.name)
            impact_result = compute_impact_for_detected_changes(modules, comparison_result)
            risk = assess_comparison_risk(impact_result["total_impacted"], len(modules))
            recommendations = generate_recommendations(comparison_result["changed_modules"], comparison_result["missing_modules"], comparison_result["added_modules"])
            st.session_state.version_comparison_result = {
                "comparison": comparison_result, "impact": impact_result, "risk": risk,
                "recommendations": recommendations, "modules": modules,
                "old_zip_name": old_zip.name, "modified_zip_name": modified_zip.name,
            }
            add_version_comparison(current_user_id(), old_zip_name=old_zip.name, modified_zip_name=modified_zip.name, comparison_result=comparison_result, impact_result=impact_result, risk=risk)
            st.session_state.processing_status = "Ready"
            st.rerun()
        except Exception as e:
            st.session_state.processing_status = "Waiting"
            st.error(f"Analysis Pipeline Aborted: {e}")
            st.rerun()
    if "version_comparison_result" not in st.session_state:
        with col_view:
            st.info("Provide source deployment boundaries to map system core delta changes.")
        return
    saved = st.session_state.version_comparison_result
    comparison_result, impact_result, risk = saved["comparison"], saved["impact"], saved["risk"]
    recommendations, modules = saved["recommendations"], saved["modules"]
    changed_modules = comparison_result.get("changed_modules", [])
    missing_modules = comparison_result.get("missing_modules", [])
    added_modules = comparison_result.get("added_modules", [])
    direct, indirect, total_impacted = impact_result.get("direct_impact", []), impact_result.get("indirect_impact", []), impact_result.get("total_impacted", [])
    with col_view:
        if missing_modules: st.markdown(warning_html(f"<b>Excised Component Hazard:</b> Removed elements tracked: {', '.join(missing_modules)}"), unsafe_allow_html=True)
        if changed_modules: st.markdown(info_html(f"<b>System Modification Event:</b> Mutated architecture blocks traced: {', '.join(changed_modules)}"), unsafe_allow_html=True)
        st.markdown('<div class="panel-header-title">📊 Variant Threat Overview</div>', unsafe_allow_html=True)
        m1, m2, m3, m4 = st.columns(4)
        with m1: st.metric("Mutated Modules", len(changed_modules))
        with m2: st.metric("Excised Modules", len(missing_modules))
        with m3: st.metric("Appended Modules", len(added_modules))
        with m4: st.markdown(f'<div class="metric-card"><div class="metric-label">Aggregated Threat Matrix</div><div class="metric-value">{risk_badge(risk)}</div></div>', unsafe_allow_html=True)
        st.markdown('<div style="margin-top:20px;"></div>', unsafe_allow_html=True)
        
        c1, c2, c3 = st.columns(3)
        with c1: st.markdown(soft_card("Detected Architecture Mutations", badge_list(changed_modules, "pill-changed")), unsafe_allow_html=True)
        with c2: st.markdown(soft_card("Excised Code Base Vectors", badge_list(missing_modules, "pill-missing")), unsafe_allow_html=True)
        with c3: st.markdown(soft_card("Appended Scope Enclosures", badge_list(added_modules, "pill-added")), unsafe_allow_html=True)
        st.markdown('<div style="margin-top:20px;"></div>', unsafe_allow_html=True)
        
        r1, r2, r3 = st.columns(3)
        with r1: st.markdown(soft_card("Immediate Impact Vectors", badge_list(direct, "pill-direct")), unsafe_allow_html=True)
        with r2: st.markdown(soft_card("Secondary Cascading Lines", badge_list(indirect, "pill-indirect")), unsafe_allow_html=True)
        with r3: st.markdown(soft_card("Blast Radius Impact Scope", risk_badge(risk)), unsafe_allow_html=True)
        st.markdown('<div style="margin-top:20px;"></div>', unsafe_allow_html=True)
        v_left, v_right = st.columns([3, 1])
        with v_left:
            st.markdown('<div class="diagnostic-matrix-card"><div class="diagnostic-card-title">🔍 Differential Structural Topology Network Map</div>', unsafe_allow_html=True)
            dot = build_comparison_dot(modules, changed_modules, missing_modules, added_modules, direct, indirect)
            st.graphviz_chart(dot, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)
        with v_right:
            st.markdown('<div class="diagnostic-matrix-card" style="height:100%;"><div class="diagnostic-card-title">🎨 Topology Map Legend</div>', unsafe_allow_html=True)
            render_graph_legend()
            st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('<div style="margin-top:20px;"></div>', unsafe_allow_html=True)
        
        rec_html = "".join(f"<li style='margin-bottom:6px; font-size:13px;'>{rec}</li>" for rec in recommendations)
        st.markdown(f'<div class="diagnostic-matrix-card"><div class="diagnostic-card-title">🛡️ System Restoration Solutions</div><ul>{rec_html}</ul></div>', unsafe_allow_html=True)
        st.markdown('<div style="margin-top:20px;"></div>', unsafe_allow_html=True)
        with st.expander("Low-Level File Manifest Delta Traces"):
            f1, f2, f3 = st.columns(3)
            with f1:
                st.markdown("**Mutated System Files**")
                if comparison_result.get("changed_files"):
                    for file in comparison_result["changed_files"]: st.caption(f"• {file}")
                else: st.caption("No package mutations traced.")
            with f2:
                st.markdown("**Purged System Files**")
                if comparison_result.get("deleted_files"):
                    for file in comparison_result["deleted_files"]: st.caption(f"• {file}")
                else: st.caption("No component purges traced.")
            with f3:
                st.markdown("**Injected System Files**")
                if comparison_result.get("added_files"):
                    for file in comparison_result["added_files"]: st.caption(f"• {file}")
                else: st.caption("No extension modules traced.")
        st.markdown('<hr>', unsafe_allow_html=True)
        st.caption(f"**Baseline Build Asset:** {saved['old_zip_name']} | **Target Code Variant:** {saved['modified_zip_name']} | **Tracked Entities:** {len(total_impacted)} modules.")
    with col_ctrl:
        try:
            comparison_html = build_version_comparison_html(saved)
            st.download_button(
                label="Download Interactive Report (HTML)", data=comparison_html,
                file_name="version_comparison_impact_report.html", mime="text/html",
                key="version_comparison_pdf_download",
            )
        except Exception as e:
            st.caption(f"Diff Compiler Offline: {e}")
def render_project_history():
    st.markdown("<h2>Platform Execution Archive Log</h2>", unsafe_allow_html=True)
    st.markdown('<p class="muted">Diagnostic ledger listing tracing history and binary alignment compilation telemetry runs.</p>', unsafe_allow_html=True)
    history = load_history(current_user_id())
    top_left, top_right = st.columns([4, 1])
    with top_right:
        if st.button("Flush Cache Registry"):
            clear_history(current_user_id())
            st.success("Execution ledger purged.")
            st.session_state.processing_status = "Waiting"
            st.rerun()
    st.markdown("### Runtime Ingestion Trace Actions")
    single_uploads = history.get("single_uploads", [])
    if not single_uploads:
        st.info("Ingestion historical telemetry layer clean.")
    else:
        for item in reversed(single_uploads):
            modules = ", ".join(item.get("modules", [])) or "None"
            missing = ", ".join(item.get("missing_modules", [])) or "None"
            html = f"""
            <b>Target Package Asset:</b> {item.get("zip_name", "-")}<br>
            <b>Ingestion Timestamp:</b> {item.get("uploaded_at", "-")}<br>
            <b>Traced Structural Nodes:</b> {item.get("total_modules", 0)} points mapped.<br>
            <b>Discovered Components:</b> {modules}<br>
            <b>Unresolved References:</b> {missing}
            """
            st.markdown(soft_card(f"Trace Snapshot Profile: {item.get('project_name', '-')}", html), unsafe_allow_html=True)
            st.markdown('<div style="margin-top:10px;"></div>', unsafe_allow_html=True)
    st.markdown("### Cross-Variant Integration Telemetry Logs")
    comparisons = history.get("version_comparisons", [])
    if not comparisons:
        st.info("System integration snapshot history registry clear.")
    else:
        for item in reversed(comparisons):
            changed = ", ".join(item.get("changed_modules", [])) or "None"
            missing = ", ".join(item.get("missing_modules", [])) or "None"
            added = ", ".join(item.get("added_modules", [])) or "None"
            direct = ", ".join(item.get("direct_impact", [])) or "None"
            indirect = ", ".join(item.get("indirect_impact", [])) or "None"
            html = f"""
            <b>Baseline Source Build:</b> {item.get("old_zip_name", "-")}<br>
            <b>Target Comparison Build:</b> {item.get("modified_zip_name", "-")}<br>
            <b>Diff Pipeline Timestamp:</b> {item.get("analyzed_at", "-")}<br>
            <b>Structural Code Mutations:</b> {changed}<br>
            <b>Excised Scope Boundaries:</b> {missing}<br>
            <b>Injected Implementations:</b> {added}<br>
            <b>Direct Traversal Paths:</b> {direct}<br>
            <b>Cascading Core Trait Risks:</b> {indirect}<br>
            <b>Aggregated Threat Evaluation Matrix:</b> {risk_badge(item.get("risk", "-"))}
            """
            st.markdown(soft_card("Cross-Version Delta Engine Execution Ledger", html), unsafe_allow_html=True)
            st.markdown('<div style="margin-top:10px;"></div>', unsafe_allow_html=True)
# ---------------------------------------------------------------------------
# Main app Layout
# ---------------------------------------------------------------------------
def do_logout():
    """Clear the session and return to the authentication pages."""
    st.session_state.logged_in = False
    st.session_state.user_id = None
    st.session_state.username = None
    st.session_state.pop("version_comparison_result", None)
    st.session_state.active_view = "Dashboard"
    st.session_state.processing_status = "Waiting"
    st.rerun()


def render_auth():
    """Login / Register pages — the only thing shown when not logged in."""
    col_l, col_c, col_r = st.columns([1, 2, 1])
    with col_c:
        st.markdown(
            """
            <div class="app-header-container" style="display:block;">
                <div class="app-meta-branding">
                    <h2 class="app-main-title">Impact <span style="color:#2563EB;">Radar</span></h2>
                    <span class="app-status-badge-pill">Secure Access</span>
                </div>
                <div class="app-meta-desc">Sign in or create an account to access your private workspace.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        tab_login, tab_register = st.tabs(["Login", "Register"])

        with tab_login:
            with st.form("login_form"):
                username = st.text_input("Username", key="login_username")
                password = st.text_input("Password", type="password", key="login_password")
                login_clicked = st.form_submit_button("Login")
            if login_clicked:
                user = authenticate_user(username, password)
                if user:
                    st.session_state.logged_in = True
                    st.session_state.user_id = user["id"]
                    st.session_state.username = user["username"]
                    st.session_state.active_view = "Dashboard"
                    st.session_state.processing_status = "Waiting"
                    st.rerun()
                else:
                    st.markdown(warning_html("Invalid username or password."), unsafe_allow_html=True)

        with tab_register:
            with st.form("register_form"):
                new_username = st.text_input("Choose a username", key="reg_username")
                new_password = st.text_input("Choose a password", type="password", key="reg_password")
                confirm_password = st.text_input("Confirm password", type="password", key="reg_password2")
                register_clicked = st.form_submit_button("Create account")
            if register_clicked:
                if new_password != confirm_password:
                    st.markdown(warning_html("Passwords do not match."), unsafe_allow_html=True)
                else:
                    ok, message = register_user(new_username, new_password)
                    if ok:
                        st.markdown(success_html(message), unsafe_allow_html=True)
                    else:
                        st.markdown(warning_html(message), unsafe_allow_html=True)


def render_dashboard():
    """Post-login landing page: welcome, totals, recent analyses, history."""
    user_id = current_user_id()
    st.markdown(f"<h2>Welcome, {st.session_state.username}</h2>", unsafe_allow_html=True)
    st.markdown('<p class="muted">Private workspace overview for your account.</p>', unsafe_allow_html=True)

    history = load_history(user_id)
    single_uploads = history.get("single_uploads", [])
    comparisons = history.get("version_comparisons", [])

    d1, d2, d3 = st.columns(3)
    with d1:
        st.metric("Total Uploaded Projects", count_projects(user_id))
    with d2:
        st.metric("Recent Analyses", len(single_uploads))
    with d3:
        st.metric("Version Comparisons", len(comparisons))

    st.markdown('<div style="margin-top:18px;"></div>', unsafe_allow_html=True)
    st.markdown('<div class="panel-header-title">Recent Analyses</div>', unsafe_allow_html=True)
    if not single_uploads:
        st.info("No analyses yet. Open Single Upload to scan your first project.")
    else:
        for item in reversed(single_uploads[-5:]):
            modules = ", ".join(item.get("modules", [])) or "None"
            missing = ", ".join(item.get("missing_modules", [])) or "None"
            html = f"""
            <b>Project:</b> {item.get('project_name', '-')}<br>
            <b>ZIP:</b> {item.get('zip_name', '-')}<br>
            <b>Uploaded:</b> {item.get('uploaded_at', '-')}<br>
            <b>Modules:</b> {modules}<br>
            <b>Missing Modules:</b> {missing}
            """
            st.markdown(soft_card("Analysis Snapshot", html), unsafe_allow_html=True)
            st.markdown('<div style="margin-top:10px;"></div>', unsafe_allow_html=True)

    st.markdown('<div class="panel-header-title">Project History</div>', unsafe_allow_html=True)
    project_names = get_project_names()
    if not project_names:
        st.info("No stored projects yet.")
    else:
        for name in project_names:
            data = get_project_data(name)
            mods = ", ".join(data.get("modules", {}).keys()) or "None"
            missing = ", ".join(data.get("missing_modules", [])) or "None"
            html = f"""
            <b>Stored Modules:</b> {mods}<br>
            <b>Missing Modules:</b> {missing}<br>
            <b>Last Updated:</b> {data.get('uploaded_at', '-')}
            """
            st.markdown(soft_card(f"Project: {name}", html), unsafe_allow_html=True)
            st.markdown('<div style="margin-top:10px;"></div>', unsafe_allow_html=True)


def main():
    # Session defaults (auth + existing app state).
    st.session_state.setdefault("logged_in", False)
    st.session_state.setdefault("user_id", None)
    st.session_state.setdefault("username", None)
    st.session_state.setdefault("active_view", "Dashboard")
    st.session_state.setdefault("processing_status", "Waiting")

    # Not authenticated -> only the login / register pages are shown.
    if not st.session_state.logged_in:
        render_auth()
        return

    with st.sidebar:
        st.markdown(
            """
            <div class="sidebar-branding">
                <h1 class="sidebar-title">Impact <span>Radar</span></h1>
                <div class="sidebar-tag">Control Console Workspace</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        is_dashboard = "nav-item-active" if st.session_state.active_view == "Dashboard" else ""
        is_single = "nav-item-active" if st.session_state.active_view == "Single Upload" else ""
        is_version = "nav-item-active" if st.session_state.active_view == "Version Change" else ""
        is_history = "nav-item-active" if st.session_state.active_view == "Project History" else ""

        if st.button("Dashboard", key="btn_dashboard", use_container_width=True, type="secondary"):
            st.session_state.active_view = "Dashboard"
            st.rerun()
        if st.button("Single Upload", key="btn_single_upload", use_container_width=True, type="secondary"):
            st.session_state.active_view = "Single Upload"
            st.rerun()
        if st.button("Version Change", key="btn_version_change", use_container_width=True, type="secondary"):
            st.session_state.active_view = "Version Change"
            st.rerun()
        if st.button("Project History", key="btn_project_history", use_container_width=True, type="secondary"):
            st.session_state.active_view = "Project History"
            st.rerun()

        st.markdown(f"""
        <style>
            div[data-testid="stSidebar"] div.stButton:nth-of-type(1) button {{
                background: {"rgba(37, 99, 235, 0.08)" if is_dashboard else "transparent"} !important;
                color: {"#2563EB" if is_dashboard else "var(--text-color)"} !important;
                font-weight: {"600" if is_dashboard else "500"} !important;
                border-left: {"4px solid #2563EB" if is_dashboard else "1px solid transparent"} !important;
                border-radius: 4px 8px 8px 4px !important; text-align: left !important; justify-content: flex-start !important;
            }}
            div[data-testid="stSidebar"] div.stButton:nth-of-type(2) button {{
                background: {"rgba(37, 99, 235, 0.08)" if is_single else "transparent"} !important;
                color: {"#2563EB" if is_single else "var(--text-color)"} !important;
                font-weight: {"600" if is_single else "500"} !important;
                border-left: {"4px solid #2563EB" if is_single else "1px solid transparent"} !important;
                border-radius: 4px 8px 8px 4px !important; text-align: left !important; justify-content: flex-start !important;
            }}
            div[data-testid="stSidebar"] div.stButton:nth-of-type(3) button {{
                background: {"rgba(37, 99, 235, 0.08)" if is_version else "transparent"} !important;
                color: {"#2563EB" if is_version else "var(--text-color)"} !important;
                font-weight: {"600" if is_version else "500"} !important;
                border-left: {"4px solid #2563EB" if is_version else "1px solid transparent"} !important;
                border-radius: 4px 8px 8px 4px !important; text-align: left !important; justify-content: flex-start !important;
            }}
            div[data-testid="stSidebar"] div.stButton:nth-of-type(4) button {{
                background: {"rgba(37, 99, 235, 0.08)" if is_history else "transparent"} !important;
                color: {"#2563EB" if is_history else "var(--text-color)"} !important;
                font-weight: {"600" if is_history else "500"} !important;
                border-left: {"4px solid #2563EB" if is_history else "1px solid transparent"} !important;
                border-radius: 4px 8px 8px 4px !important; text-align: left !important; justify-content: flex-start !important;
            }}
        </style>
        """, unsafe_allow_html=True)

        st.markdown('<hr>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="muted" style="padding:0 4px 8px 4px;">Signed in as '
            f'<b>{st.session_state.username}</b></div>',
            unsafe_allow_html=True,
        )
        if st.button("Logout", key="btn_logout", use_container_width=True):
            do_logout()

        st.markdown('<div style="position: fixed; bottom: 20px; font-size:11px; opacity:0.5;">Core: 2.4.1 Stable<br>Telemetry Trace: Connected</div>', unsafe_allow_html=True)

    st.markdown(
        f"""
        <div class="app-header-container">
            <div>
                <div class="app-meta-branding">
                    <h2 class="app-main-title">{st.session_state.active_view}</h2>
                    <span class="app-status-badge-pill">Operational Session</span>
                </div>
                <div class="app-meta-desc">Automated system topology tracing utility panel and structural change tracking engine.</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.session_state.active_view == "Dashboard":
        render_dashboard()
        return

    st.markdown("<br>", unsafe_allow_html=True)

    if st.session_state.active_view == "Single Upload":
        render_single_zip_analysis()
    elif st.session_state.active_view == "Version Change":
        render_version_comparison_analysis()
    elif st.session_state.active_view == "Project History":
        render_project_history()


if __name__ == "__main__":
    main()
