import pandas as pd
import pytest

from app.pipeline.profile import infer_column_type, profile_columns
from app.pipeline.validate import validate_rows


def test_infers_integer_from_majority():
    series = pd.Series([3, "two", 5, 2, 1])
    assert infer_column_type(series) == "integer"


def test_falls_back_to_text_when_no_type_dominates():
    series = pd.Series(["alpha", "beta", "2026-01-01"])
    assert infer_column_type(series) == "text"


def test_infers_date():
    series = pd.Series(["2026-01-05", "2026-01-06", "2026-01-07"])
    assert infer_column_type(series) == "date"


def test_flags_value_that_breaks_inferred_type():
    df = pd.DataFrame({"units": [3, "two", 5, 2, 1], "price": [10.0] * 5})
    columns = profile_columns(df)
    records = validate_rows(df, columns)

    assert records[0]["is_valid"] is True
    assert records[1]["is_valid"] is False
    assert records[1]["issues"][0]["column"] == "units"
    assert "whole number" in records[1]["issues"][0]["message"]


def test_empty_required_value_is_flagged():
    df = pd.DataFrame({"customer": ["Acme", None]})
    columns = profile_columns(df)
    records = validate_rows(df, columns, required_columns=["customer"])

    assert records[1]["is_valid"] is False
    assert records[1]["issues"][0]["message"] == "Required value is missing"


def test_optional_empty_value_is_not_flagged():
    df = pd.DataFrame({"customer": ["Acme", None], "amount": [10, 12]})
    columns = profile_columns(df)
    records = validate_rows(df, columns)

    assert records[1]["is_valid"] is True
    assert records[1]["data"]["customer"] is None


def test_blank_row_is_flagged():
    df = pd.DataFrame({"a": [1, None], "b": ["x", None]})
    columns = profile_columns(df)
    records = validate_rows(df, columns)

    assert records[1]["is_valid"] is False
    assert records[1]["issues"][0]["message"] == "Row is empty"


def test_dates_are_normalized_to_iso():
    df = pd.DataFrame({"day": ["05/01/2026"]})
    columns = profile_columns(df)
    records = validate_rows(df, columns)

    assert records[0]["data"]["day"] == "2026-01-05"


def test_numbers_with_commas_are_normalized():
    df = pd.DataFrame({"amount": ["1,250.50", "980"]})
    columns = profile_columns(df)
    records = validate_rows(df, columns)

    assert records[0]["data"]["amount"] == 1250.5


def test_duplicate_business_key_flags_both_rows():
    df = pd.DataFrame({"order_id": ["A-1", "B-2", "A-1"], "amount": [10, 20, 30]})
    columns = profile_columns(df)
    records = validate_rows(df, columns, unique_columns=["order_id"])

    assert records[0]["is_valid"] is False
    assert records[1]["is_valid"] is True
    assert records[2]["is_valid"] is False
    assert "also in row 3" in records[0]["issues"][0]["message"]
    assert "first seen in row 1" in records[2]["issues"][0]["message"]


def test_missing_business_key_is_not_a_duplicate():
    df = pd.DataFrame({"order_id": [None, None], "amount": [10, 20]})
    columns = profile_columns(df)
    records = validate_rows(df, columns, unique_columns=["order_id"])

    assert all(record["is_valid"] for record in records)
