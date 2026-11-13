"""PDF report: summary, metrics, a sample of clean rows, and flagged rows."""

from datetime import datetime, timezone
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Table,
    TableStyle,
)

from .analytics import build_dashboard

ACCENT = colors.HexColor("#0F766E")
INK = colors.HexColor("#1F2933")
MUTED = colors.HexColor("#616E7C")
WARN_BG = colors.HexColor("#FFF4E6")

MAX_ROWS = 30
MAX_FLAGGED = 20
MAX_COLUMNS = 6


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "Title", parent=base["Title"], fontName="Helvetica-Bold", fontSize=20,
            textColor=INK, alignment=0, spaceAfter=4,
        ),
        "subtitle": ParagraphStyle(
            "Subtitle", parent=base["Normal"], fontSize=9, textColor=MUTED, spaceAfter=14,
        ),
        "heading": ParagraphStyle(
            "Heading", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=12,
            textColor=ACCENT, spaceBefore=12, spaceAfter=6,
        ),
        "body": ParagraphStyle("Body", parent=base["Normal"], fontSize=9, textColor=INK),
        "cell": ParagraphStyle("Cell", parent=base["Normal"], fontSize=7.5, leading=9.5, textColor=INK),
        "cell_small": ParagraphStyle(
            "CellSmall", parent=base["Normal"], fontSize=7, leading=8.5, textColor=MUTED
        ),
    }


def _table(data, widths=None, header=True, row_colors=None):
    table = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    style = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D9E2EC")),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    if header:
        style += [
            ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ]
    if row_colors:
        style += row_colors
    table.setStyle(TableStyle(style))
    return table


def _issue_text(issues) -> str:
    parts = []
    for issue in issues or []:
        if issue.get("column"):
            parts.append(f"{issue['column']}: {issue['message']}")
        else:
            parts.append(issue["message"])
    return "; ".join(parts)


def build_pdf(filename: str, columns: list[dict], rows) -> BytesIO:
    styles = _styles()
    dashboard = build_dashboard(columns, rows)
    clean_rows = [row for row in rows if row.is_valid]
    flagged_rows = [row for row in rows if not row.is_valid]

    stream = BytesIO()
    doc = SimpleDocTemplate(
        stream,
        pagesize=landscape(A4),
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        title=f"DataPilot report — {filename}",
    )

    story = [
        Paragraph("DataPilot report", styles["title"]),
        Paragraph(
            f"{filename} · exported {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
            styles["subtitle"],
        ),
    ]

    summary_data = [
        ["Rows", "Clean rows", "Flagged rows", "Columns"],
        [str(len(rows)), str(len(clean_rows)), str(len(flagged_rows)), str(len(columns))],
    ]
    story.append(_table(summary_data, header=True))

    if dashboard["metrics"]:
        story.append(Paragraph("Totals", styles["heading"]))
        metric_data = [["Metric", "Total"]] + [
            [metric["name"], f"{metric['total']:,.2f}"] for metric in dashboard["metrics"]
        ]
        story.append(_table(metric_data))

    if dashboard["by_dimension"]:
        series = dashboard["by_dimension"]
        story.append(Paragraph(f"{series['metric']} by {dashboard['dimension']}", styles["heading"]))
        breakdown = [["Category", series["metric"]]] + [
            [label, f"{value:,.2f}"] for label, value in zip(series["labels"], series["values"])
        ]
        story.append(_table(breakdown))

    story.append(Paragraph("Clean data", styles["heading"]))
    if clean_rows:
        headers = [column["name"] for column in columns[:MAX_COLUMNS]]
        data = [headers]
        for row in clean_rows[:MAX_ROWS]:
            data.append(
                [
                    Paragraph(str(row.data.get(name, "")).replace("\n", " "), styles["cell"])
                    for name in headers
                ]
            )
        story.append(_table(data))
        if len(clean_rows) > MAX_ROWS:
            story.append(
                Paragraph(
                    f"Showing {MAX_ROWS} of {len(clean_rows)} clean rows. "
                    f"{'Only the first ' + str(MAX_COLUMNS) + ' columns are shown. ' if len(columns) > MAX_COLUMNS else ''}"
                    "Download the Excel report for the full data.",
                    styles["cell_small"],
                )
            )
    else:
        story.append(Paragraph("No clean rows.", styles["body"]))

    if flagged_rows:
        story.append(PageBreak())
        story.append(Paragraph("Flagged rows", styles["heading"]))
        headers = ["#"] + [column["name"] for column in columns[:MAX_COLUMNS - 1]] + ["Issues"]
        data = [headers]
        for row in flagged_rows[:MAX_FLAGGED]:
            data.append(
                [str(row.row_number)]
                + [
                    Paragraph(str(row.data.get(name, "")).replace("\n", " "), styles["cell"])
                    for name in headers[1:-1]
                ]
                + [Paragraph(_issue_text(row.issues), styles["cell"])]
            )
        row_colors = [
            ("BACKGROUND", (0, index), (-1, index), WARN_BG)
            for index in range(1, len(data))
        ]
        story.append(_table(data, row_colors=row_colors))
        if len(flagged_rows) > MAX_FLAGGED:
            story.append(
                Paragraph(
                    f"Showing {MAX_FLAGGED} of {len(flagged_rows)} flagged rows.",
                    styles["cell_small"],
                )
            )

    doc.build(story)
    stream.seek(0)
    return stream
