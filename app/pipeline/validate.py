"""Turn raw DataFrame cells into typed values and flag rows that break the pattern."""

from datetime import date, datetime

import pandas as pd

from .profile import DATE_FORMATS


def is_blank(value) -> bool:
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass
    return str(value).strip() == ""


def _coerce(value, column_type):
    """Return (ok, normalized_value, error_message)."""
    if column_type == "integer":
        if isinstance(value, bool):
            return False, None, "Expected a whole number"
        if isinstance(value, int):
            return True, value, None
        if isinstance(value, float) and value.is_integer():
            return True, int(value), None
        text = str(value).strip().replace(",", "")
        try:
            return True, int(text), None
        except ValueError:
            return False, None, f"Expected a whole number, got {str(value).strip()!r}"

    if column_type == "number":
        if isinstance(value, bool):
            return False, None, "Expected a number"
        if isinstance(value, (int, float)):
            return True, float(value), None
        text = str(value).strip().replace(",", "").replace("$", "")
        try:
            return True, float(text), None
        except ValueError:
            return False, None, f"Expected a number, got {str(value).strip()!r}"

    if column_type == "date":
        if isinstance(value, datetime):
            return True, value.date().isoformat(), None
        if isinstance(value, date):
            return True, value.isoformat(), None
        text = str(value).strip()
        for fmt in DATE_FORMATS:
            try:
                parsed = pd.to_datetime(text, format=fmt)
                return True, parsed.date().isoformat(), None
            except (ValueError, TypeError):
                continue
        return False, None, f"Expected a date, got {text!r}"

    return True, str(value).strip(), None


def validate_rows(
    df: pd.DataFrame,
    columns: list[dict],
    required_columns=(),
    unique_columns=(),
) -> list[dict]:
    """Return one record per data row, with typed data and a list of issues.

    unique_columns names business keys (e.g. order_id). A repeated key flags both
    the first occurrence and the duplicate, because either could be the wrong row.
    """
    df = df.reset_index(drop=True)
    type_by_name = {str(col): info["type"] for col, info in zip(df.columns, columns)}
    required = set(required_columns)
    unique = [str(name) for name in unique_columns if str(name) in df.columns]
    first_seen: dict[tuple, dict] = {}

    records = []
    for index, raw_row in df.iterrows():
        data = {}
        issues = []
        every_cell_blank = True

        for column in df.columns:
            name = str(column)
            value = raw_row[column]

            if not is_blank(value):
                every_cell_blank = False

            if is_blank(value):
                data[name] = None
                if name in required:
                    issues.append({"column": name, "message": "Required value is missing"})
                continue

            ok, normalized, error = _coerce(value, type_by_name[name])
            data[name] = normalized
            if not ok:
                issues.append({"column": name, "message": error})

        if every_cell_blank:
            issues.append({"column": None, "message": "Row is empty"})

        record = {
            "row_number": index + 1,
            "data": data,
            "is_valid": not issues,
            "issues": issues,
        }

        if unique and all(data.get(name) is not None for name in unique):
            key = tuple(data[name] for name in unique)
            label = ", ".join(f"{name}={data[name]!r}" for name in unique)
            if key in first_seen:
                first = first_seen[key]
                duplicate_message = (
                    f"Duplicate {label} (first seen in row {first['row_number']})"
                )
                issue = {"column": unique[0], "message": duplicate_message}
                record["issues"].append(issue)
                record["is_valid"] = False

                first["issues"].append(
                    {
                        "column": unique[0],
                        "message": f"Duplicate {label} (also in row {record['row_number']})",
                    }
                )
                first["is_valid"] = False
            else:
                first_seen[key] = record

        records.append(record)

    return records
