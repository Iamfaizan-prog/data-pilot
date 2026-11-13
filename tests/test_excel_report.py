from types import SimpleNamespace

from openpyxl import load_workbook

from app.reports.excel import build_excel, escape_formula

COLUMNS = [
    {"name": "order_id", "type": "text"},
    {"name": "amount", "type": "number"},
]


def _rows():
    return [
        SimpleNamespace(
            data={"order_id": "A-1", "amount": 10.0},
            is_valid=True,
            issues=[],
        ),
        SimpleNamespace(
            data={"order_id": "B-2", "amount": None},
            is_valid=False,
            issues=[{"column": "amount", "message": "Expected a number, got 'x'"}],
        ),
    ]


def test_workbook_has_summary_clean_and_flagged_sheets():
    stream = build_excel("sales.csv", COLUMNS, _rows())
    workbook = load_workbook(stream)

    assert workbook.sheetnames == ["Summary", "Clean data", "Flagged"]


def test_clean_rows_and_flagged_rows_are_separated():
    stream = build_excel("sales.csv", COLUMNS, _rows())
    workbook = load_workbook(stream)

    clean = workbook["Clean data"]
    flagged = workbook["Flagged"]

    assert clean.max_row == 2  # header + one clean row
    assert clean["A2"].value == "A-1"

    assert flagged.max_row == 2  # header + one flagged row
    assert flagged["A2"].value == "B-2"
    assert "amount" in flagged["C2"].value
    assert "Expected a number" in flagged["C2"].value


def test_summary_counts_rows():
    stream = build_excel("sales.csv", COLUMNS, _rows())
    workbook = load_workbook(stream)
    summary = workbook["Summary"]

    values = {summary.cell(row=row, column=1).value: summary.cell(row=row, column=2).value for row in range(2, 7)}
    assert values["Rows"] == 2
    assert values["Clean rows"] == 1
    assert values["Flagged rows"] == 1


def test_formula_cells_are_escaped():
    assert escape_formula("=1+1") == "'=1+1"
    assert escape_formula("+SUM(A1)") == "'+SUM(A1)"
    assert escape_formula("-2") == "'-2"
    assert escape_formula("@cmd") == "'@cmd"
    assert escape_formula("A-1") == "A-1"
    assert escape_formula(10) == 10

    rows = [
        SimpleNamespace(
            data={"order_id": "=HYPERLINK(\"http://example.com\")", "amount": 10.0},
            is_valid=True,
            issues=[],
        )
    ]
    stream = build_excel("sales.csv", COLUMNS, rows)
    workbook = load_workbook(stream)

    assert workbook["Clean data"]["A2"].value.startswith("'=")
