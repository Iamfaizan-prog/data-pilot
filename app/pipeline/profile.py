"""Infer a type for each column.

Client files often contain one bad cell among good ones. We therefore infer from
the majority pattern and let validation flag the outliers, instead of letting a
single bad cell turn the whole column into text.
"""

import pandas as pd

MIN_TYPE_CONFIDENCE = 0.7

DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%m/%d/%Y",
)


def _blank(value) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and pd.isna(value):
        return True
    return str(value).strip() == ""


def _is_integer(value) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    text = str(value).strip()
    try:
        int(text)
        return True
    except ValueError:
        return False


def _is_number(value) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return True
    text = str(value).strip().replace(",", "").replace("$", "")
    try:
        float(text)
        return True
    except ValueError:
        return False


def _is_date(value) -> bool:
    if isinstance(value, (pd.Timestamp,)):
        return True
    text = str(value).strip()
    for fmt in DATE_FORMATS:
        try:
            pd.to_datetime(text, format=fmt)
            return True
        except (ValueError, TypeError):
            continue
    return False


CHECKS = {
    "integer": _is_integer,
    "number": _is_number,
    "date": _is_date,
}


def infer_column_type(series: pd.Series) -> str:
    values = [value for value in series.tolist() if not _blank(value)]
    if not values:
        return "text"

    scores = {name: sum(check(v) for v in values) / len(values) for name, check in CHECKS.items()}
    # Prefer the most specific type when scores tie (integer before number).
    for name in ("integer", "number", "date"):
        if scores[name] >= MIN_TYPE_CONFIDENCE:
            return name
    return "text"


def profile_columns(df: pd.DataFrame) -> list[dict]:
    columns = []
    for name in df.columns:
        series = df[name]
        columns.append(
            {
                "name": str(name),
                "type": infer_column_type(series),
                "null_count": int(series.isna().sum()),
                "unique_count": int(series.nunique(dropna=True)),
            }
        )
    return columns
