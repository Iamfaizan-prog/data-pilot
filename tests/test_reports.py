from types import SimpleNamespace

from app.reports.analytics import build_dashboard
from app.reports.pdf import build_pdf

COLUMNS = [
    {"name": "order_id", "type": "text"},
    {"name": "region", "type": "text"},
    {"name": "order_date", "type": "date"},
    {"name": "units", "type": "integer"},
    {"name": "unit_price", "type": "number"},
]


def _row(number, order_id, region, day, units, price, valid=True):
    return SimpleNamespace(
        row_number=number,
        data={
            "order_id": order_id,
            "region": region,
            "order_date": day,
            "units": units,
            "unit_price": price,
        },
        is_valid=valid,
        issues=[] if valid else [{"column": "units", "message": "bad"}],
    )


def _rows():
    return [
        _row(1, "A-1", "North", "2026-01-05", 1, 10.0),
        _row(2, "B-2", "South", "2026-01-05", 2, 20.0),
        _row(3, "C-3", "North", "2026-01-06", 3, 30.0),
        _row(4, "D-4", "South", "2026-01-06", 999, 999.0, valid=False),
    ]


def test_dashboard_uses_only_valid_rows():
    result = build_dashboard(COLUMNS, _rows())

    assert result["row_count"] == 3
    totals = {metric["name"]: metric["total"] for metric in result["metrics"]}
    assert totals["units"] == 6.0
    assert totals["unit_price"] == 60.0


def test_dashboard_picks_first_text_dimension_and_sums_by_it():
    result = build_dashboard(COLUMNS, _rows())

    assert result["dimension"] == "region"
    assert result["by_dimension"]["labels"] == ["North", "South"]
    assert result["by_dimension"]["values"] == [4.0, 2.0]


def test_dashboard_builds_time_series():
    result = build_dashboard(COLUMNS, _rows())

    assert result["date_column"] == "order_date"
    assert result["by_date"]["labels"] == ["2026-01-05", "2026-01-06"]
    assert result["by_date"]["values"] == [3.0, 3.0]


def test_pdf_starts_with_pdf_header():
    stream = build_pdf("sales.csv", COLUMNS, _rows())
    content = stream.read()

    assert content.startswith(b"%PDF")
    assert len(content) > 1000
