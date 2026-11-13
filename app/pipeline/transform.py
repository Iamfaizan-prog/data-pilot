"""Cleaning steps applied after validation and before storage."""


def _clean_text(value):
    if not isinstance(value, str):
        return value
    cleaned = " ".join(value.split())
    return cleaned or None


def transform_records(records: list[dict], columns: list[dict]) -> list[dict]:
    """Apply safe, reversible cleaning to typed records.

    Only whitespace is normalized. Case, currency symbols, and business values are
    left alone because changing them can change what the data means.
    """
    text_columns = [column["name"] for column in columns if column["type"] == "text"]
    for record in records:
        for name in text_columns:
            if name in record["data"]:
                record["data"][name] = _clean_text(record["data"][name])
    return records
