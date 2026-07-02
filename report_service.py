"""
report_service — builds a rich, visual PDF impact-analysis report.

The PDF embeds:
  * a KPI summary table,
  * an impact-distribution bar chart,
  * a risk / blast-radius donut chart,
  * a colour-coded dependency graph,
  * affected-module lists (with an explicit "no dependencies" message),
  * a testing recommendation.

Public API:
    build_pdf_report(report: dict) -> bytes

`report` is the snapshot stored in st.session_state.report and must contain:
    project, changed_module, direct, indirect, total_impacted,
    risk, generated_at, modules
"""

from io import BytesIO
import math

import matplotlib
matplotlib.use("Agg")  # headless — never touch a display
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
)

# --- palette (kept readable on a white PDF page) ---------------------------
ACCENT = "#6366f1"
RED = "#ef4444"
AMBER = "#f59e0b"
GREEN = "#22c55e"
GREY = "#94a3b8"
INK = "#1f2937"
SUBTLE = "#64748b"

RISK_COLORS = {"HIGH": RED, "MEDIUM": AMBER, "LOW": GREEN}


# ---------------------------------------------------------------------------
# Chart builders (each returns a BytesIO PNG)
# ---------------------------------------------------------------------------
def _impact_bar_chart(direct, indirect, unaffected):
    fig, ax = plt.subplots(figsize=(4.2, 3.0), dpi=160)
    labels = ["Direct", "Indirect", "Unaffected"]
    values = [direct, indirect, unaffected]
    bars = ax.bar(labels, values, color=[RED, AMBER, GREY], width=0.6,
                  edgecolor="white", linewidth=0.5)
    ax.set_title("Impact distribution", fontsize=11, fontweight="bold",
                 color=INK, pad=10)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color("#cbd5e1")
    ax.tick_params(colors=SUBTLE, labelsize=9)
    ax.set_ylim(0, max(values + [1]) * 1.25)
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                str(val), ha="center", va="bottom", fontsize=10,
                fontweight="bold", color=INK)
    fig.tight_layout()
    return _fig_to_buffer(fig)


def _risk_donut(impacted, total, risk):
    fig, ax = plt.subplots(figsize=(4.2, 3.0), dpi=160)
    denom = max(total - 1, 1)
    impacted = min(impacted, denom)
    safe = denom - impacted
    ratio = impacted / denom
    color = RISK_COLORS.get(risk, GREY)
    ax.pie(
        [impacted, safe] if (impacted + safe) > 0 else [1],
        colors=[color, "#e5e7eb"] if (impacted + safe) > 0 else ["#e5e7eb"],
        startangle=90, counterclock=False,
        wedgeprops=dict(width=0.38, edgecolor="white"),
    )
    ax.text(0, 0.12, f"{ratio * 100:.0f}%", ha="center", va="center",
            fontsize=20, fontweight="bold", color=color)
    ax.text(0, -0.22, "blast radius", ha="center", va="center",
            fontsize=9, color=SUBTLE)
    ax.set_title(f"Risk: {risk}", fontsize=11, fontweight="bold",
                 color=color, pad=10)
    fig.tight_layout()
    return _fig_to_buffer(fig)


def _dependency_graph_image(modules, changed, direct, indirect, missing_nodes=None):
    """Circular-layout dependency graph drawn purely with matplotlib."""
    missing_nodes = set(missing_nodes or [])
    names = list(modules.keys())
    n = len(names)
    fig, ax = plt.subplots(figsize=(7.2, 4.6), dpi=160)
    ax.axis("off")
    ax.set_title("Dependency graph", fontsize=11, fontweight="bold",
                 color=INK, pad=8, loc="left")

    if n == 0:
        ax.text(0.5, 0.5, "No modules to display", ha="center",
                va="center", fontsize=11, color=SUBTLE)
        return _fig_to_buffer(fig)

    # Position nodes on a circle (single node -> centre).
    pos = {}
    if n == 1:
        pos[names[0]] = (0.0, 0.0)
    else:
        for i, name in enumerate(names):
            angle = 2 * math.pi * i / n
            pos[name] = (math.cos(angle), math.sin(angle))

    # Edges: dependency -> dependent (matches the on-screen graph).
    for module, deps in modules.items():
        for dep in deps:
            if dep in pos and module in pos and dep != module:
                x1, y1 = pos[dep]
                x2, y2 = pos[module]
                is_missing_edge = dep in missing_nodes
                ax.add_patch(FancyArrowPatch(
                    (x1, y1), (x2, y2),
                    connectionstyle="arc3,rad=0.08",
                    arrowstyle="-|>", mutation_scale=10,
                    color=RED if is_missing_edge else "#cbd5e1",
                    linewidth=1.8 if is_missing_edge else 0.9,
                    linestyle="--" if is_missing_edge else "-",
                    shrinkA=12, shrinkB=12, zorder=1,
                ))

    # Label sits just below the node in dark ink with a faint white
    # backing box, so it stays readable no matter how long the name is
    # (white-on-node text used to spill off the marker and vanish).
    label_offset = 0.16 if n > 1 else 0.22
    for name, (x, y) in pos.items():
        is_missing = name in missing_nodes
        if is_missing:
            fill, edge = RED, "#7f1d1d"
        elif name == changed:
            fill, edge = ACCENT, "#4338ca"
        elif name in direct:
            fill, edge = RED, "#b91c1c"
        elif name in indirect:
            fill, edge = AMBER, "#b45309"
        else:
            fill, edge = "#f1f5f9", "#cbd5e1"
        ax.scatter([x], [y], s=620 if is_missing else 520, c=fill, edgecolors=edge,
                   linewidths=2.2 if is_missing else 1.4, zorder=2)
        label_text = f"{name}\nMISSING" if is_missing else name
        label = label_text if len(label_text) <= 18 else label_text[:16] + "…"
        ax.text(x, y - label_offset, label, ha="center", va="top",
                fontsize=7, fontweight="bold", color=INK, zorder=3,
                bbox=dict(boxstyle="round,pad=0.15", fc="white",
                          ec="none", alpha=0.75))

    pad = 1.45 if n > 1 else 0.6
    ax.set_xlim(-pad, pad)
    ax.set_ylim(-pad, pad)
    ax.set_aspect("equal")

    # Legend
    handles = [
        plt.Line2D([0], [0], marker="o", color="w", label="Changed",
                   markerfacecolor=ACCENT, markersize=9),
        plt.Line2D([0], [0], marker="o", color="w", label="Direct",
                   markerfacecolor=RED, markersize=9),
        plt.Line2D([0], [0], marker="o", color="w", label="Indirect",
                   markerfacecolor=AMBER, markersize=9),
        plt.Line2D([0], [0], marker="o", color="w", label="Missing/Error",
                   markerfacecolor=RED, markeredgecolor="#7f1d1d",
                   markersize=9),
        plt.Line2D([0], [0], marker="o", color="w", label="Unaffected",
                   markerfacecolor="#f1f5f9", markeredgecolor="#cbd5e1",
                   markersize=9),
    ]
    ax.legend(handles=handles, loc="lower center", ncol=5, frameon=False,
              fontsize=8, bbox_to_anchor=(0.5, -0.04))
    fig.tight_layout()
    return _fig_to_buffer(fig)


def _fig_to_buffer(fig):
    buf = BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight",
                facecolor="white", dpi=160)
    plt.close(fig)
    buf.seek(0)
    return buf


# ---------------------------------------------------------------------------
# PDF assembly
# ---------------------------------------------------------------------------
def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "IRTitle", parent=base["Title"], fontSize=22, leading=26,
            textColor=colors.HexColor(INK), spaceAfter=2, alignment=TA_LEFT),
        "subtitle": ParagraphStyle(
            "IRSub", parent=base["Normal"], fontSize=10,
            textColor=colors.HexColor(SUBTLE), spaceAfter=10),
        "h2": ParagraphStyle(
            "IRH2", parent=base["Heading2"], fontSize=13,
            textColor=colors.HexColor(INK), spaceBefore=12, spaceAfter=6),
        "body": ParagraphStyle(
            "IRBody", parent=base["Normal"], fontSize=10, leading=15,
            textColor=colors.HexColor(INK)),
        "muted": ParagraphStyle(
            "IRMuted", parent=base["Normal"], fontSize=10, leading=15,
            textColor=colors.HexColor(SUBTLE)),
        "callout": ParagraphStyle(
            "IRCallout", parent=base["Normal"], fontSize=10, leading=15,
            textColor=colors.HexColor("#92400e")),
    }


def _kpi_table(total, direct, indirect, impacted):
    data = [
        ["Total modules", "Direct dependents",
         "Indirect dependents", "Total impacted"],
        [str(total), str(direct), str(indirect), str(impacted)],
    ]
    tbl = Table(data, colWidths=[42 * mm] * 4)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor(SUBTLE)),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("FONTSIZE", (0, 1), (-1, 1), 18),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 1), (-1, 1), colors.HexColor(INK)),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
    ]))
    return tbl


def _meta_table(report, styles):
    risk = report["risk"]
    risk_color = RISK_COLORS.get(risk, GREY)
    rows = [
        ["Project", report["project"]],
        ["Changed module", report["changed_module"]],
        ["Generated", report["generated_at"]],
        ["Risk level", risk],
    ]
    tbl = Table(rows, colWidths=[40 * mm, 130 * mm])
    style = [
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor(SUBTLE)),
        ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor(INK)),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, colors.HexColor("#e2e8f0")),
        # highlight the risk value
        ("TEXTCOLOR", (1, 3), (1, 3), colors.HexColor(risk_color)),
        ("FONTNAME", (1, 3), (1, 3), "Helvetica-Bold"),
    ]
    tbl.setStyle(TableStyle(style))
    return tbl


def build_pdf_report(report):
    """Render the impact report to PDF bytes."""
    styles = _styles()
    modules = report.get("modules", {})
    missing_nodes = set(report.get("missing_nodes", []))
    changed = report["changed_module"]
    direct = list(report["direct"])
    indirect = list(report["indirect"])
    total = len(modules)
    impacted = report["total_impacted"]
    unaffected = max(total - impacted - 1, 0)  # exclude the changed module
    risk = report["risk"]

    if risk == "HIGH":
        recommendation = "Full regression testing is recommended."
    elif risk == "MEDIUM":
        recommendation = "Targeted regression testing is recommended."
    else:
        recommendation = "Minimal testing is sufficient."

    own_deps = modules.get(changed, [])

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=16 * mm, bottomMargin=16 * mm,
        title="Impact Analysis Report",
    )
    story = []

    # Accent header bar
    bar = Table([[""]], colWidths=[174 * mm], rowHeights=[3])
    bar.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(ACCENT))]))
    story += [bar, Spacer(1, 8)]

    story.append(Paragraph("Impact Analysis Report", styles["title"]))
    story.append(Paragraph(
        "Change-impact assessment generated by Impact Radar.",
        styles["subtitle"]))

    story.append(_meta_table(report, styles))
    if missing_nodes:
        story.append(Paragraph(
            "<b>Controlled validation error:</b> missing business module(s): " + ", ".join(sorted(missing_nodes)),
            styles["callout"]))
    story.append(Spacer(1, 12))

    story.append(_kpi_table(total, len(direct), len(indirect), impacted))
    story.append(Spacer(1, 14))

    # Charts row (bar + donut)
    bar_img = Image(_impact_bar_chart(len(direct), len(indirect), unaffected),
                    width=82 * mm, height=58 * mm)
    donut_img = Image(_risk_donut(impacted, total, risk),
                      width=82 * mm, height=58 * mm)
    charts = Table([[bar_img, donut_img]], colWidths=[87 * mm, 87 * mm])
    charts.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    story.append(charts)
    story.append(Spacer(1, 10))

    # Dependency graph
    graph_img = Image(
        _dependency_graph_image(modules, changed, set(direct), set(indirect), missing_nodes),
        width=170 * mm, height=108 * mm)
    story.append(graph_img)
    story.append(Spacer(1, 6))

    # --- Affected modules -------------------------------------------------
    story.append(Paragraph("Directly affected modules", styles["h2"]))
    if direct:
        for m in direct:
            story.append(Paragraph(f"&bull;&nbsp; {m}", styles["body"]))
    else:
        story.append(Paragraph(
            "No directly dependent modules — no module imports "
            f"<b>{changed}</b>.", styles["muted"]))

    story.append(Paragraph("Indirectly affected modules", styles["h2"]))
    if indirect:
        for m in indirect:
            story.append(Paragraph(f"&bull;&nbsp; {m}", styles["body"]))
    else:
        story.append(Paragraph(
            "No indirectly dependent modules.", styles["muted"]))

    # --- Explicit no-dependency callout -----------------------------------
    if impacted == 0:
        story.append(Spacer(1, 8))
        callout = Table([[Paragraph(
            f"<b>No dependencies found.</b> Nothing depends on "
            f"<b>{changed}</b>, so this change has no downstream impact "
            "and is safe to ship.", styles["callout"])]],
            colWidths=[174 * mm])
        callout.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fef3c7")),
            ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#fcd34d")),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(callout)

    # Module's own dependencies note
    story.append(Spacer(1, 8))
    if own_deps:
        uniq = ", ".join(sorted(set(own_deps)))
        story.append(Paragraph(
            f"<b>{changed}</b> itself depends on: {uniq}.", styles["muted"]))
    else:
        story.append(Paragraph(
            f"<b>{changed}</b> has no outgoing dependencies of its own.",
            styles["muted"]))

    # --- Recommendation ---------------------------------------------------
    story.append(Paragraph("Recommendation", styles["h2"]))
    rec = Table([[Paragraph(
        f"<b>Total impacted modules: {impacted}.</b> {recommendation}",
        styles["body"])]], colWidths=[174 * mm])
    rec.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#eef2ff")),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#c7d2fe")),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(rec)

    doc.build(story)
    buf.seek(0)
    return buf.getvalue()
