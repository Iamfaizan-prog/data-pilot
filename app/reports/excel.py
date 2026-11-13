"""Build an Excel workbook from an import.

Two data sheets keep the promise the UI makes: clean rows stay usable, and
flagged rows remain visible with their reasons instead of disappearing.
"""

from datetime import datetime, timezone
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

HEADER_FILL = PatternFill("solid", fgColor="0F766E")
HEADER_FONT = Font(color="FFFFFF", bold=True)
FLAG_FILL = PatternFill("solid", fgColor="FFF4E6")
FLAG_FONT = Font(color="8A4B08")


def escape_formula(value):
    """Stop spreadsheet formula execution in exported text cells."""
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def _issue_text(issues) -> str:
    parts = []
    for issue in issues or []:
        if issue.get("column"):
            parts.append(f"{issue['column']}: {issue['message']}")
        else:
            parts.append(issue["message"])
    return "; ".join(parts)


def _write_sheet(worksheet, headers, rows, include_issues=False):
    all_headers = headers + (["Issues"] if include_issues else [])
    worksheet.append([escape_formula(value) for value in all_headers])

    for cell in worksheet[1]:
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(vertical="center")

    for row in rows:
        values = [escape_formula(row.data.get(name)) for name in headers]
        if include_issues:
            values.append(escape_formula(_issue_text(row.issues)))
        worksheet.append(values)

        if not row.is_valid:
            for cell in worksheet[worksheet.max_row]:
                cell.fill = FLAG_FILL
                if include_issues:
                    cell.font = FLAG_FONT
                    cell.alignment = Alignment(wrap_text=True, vertical="top")

    worksheet.freeze_panes = "A2"
    for index, name in enumerate(all_headers, start=1):
        if include_issues and name == "Issues":
            values = [_issue_text(row.issues) for row in rows]
        else:
            values = [row.data.get(name) for row in rows]
        longest = max(
            [len(str(name))] + [len(str(value)) for value in values if value is not None]
        )
        worksheet.column_dimensions[get_column_letter(index)].width = min(
            max(longest + 2, 12), 45
        )


def build_excel(filename: str, columns: list[dict], rows) -> BytesIO:
    headers = [column["name"] for column in columns]
    clean_rows = [row for row in rows if row.is_valid]
    flagged_rows = [row for row in rows if not row.is_valid]

    workbook = Workbook()

    summary = workbook.active
    summary.title = "Summary"
    summary.append(["DataPilot export"])
    summary["A1"].font = Font(bold=True, size=14)
    summary.append(["File", escape_formula(filename)])
    summary.append(["Rows", len(rows)])
    summary.append(["Clean rows", len(clean_rows)])
    summary.append(["Flagged rows", len(flagged_rows)])
    summary.append(["Exported at", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")])
    summary.column_dimensions["A"].width = 16
    summary.column_dimensions["B"].width = 42

    clean_sheet = workbook.create_sheet("Clean data")
    _write_sheet(clean_sheet, headers, clean_rows)

    flagged_sheet = workbook.create_sheet("Flagged")
    _write_sheet(flagged_sheet, headers, flagged_rows, include_issues=True)

    stream = BytesIO()
    workbook.save(stream)
    stream.seek(0)
    return stream
