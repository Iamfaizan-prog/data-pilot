import pandas as pd

from app.pipeline.profile import profile_columns
from app.pipeline.transform import transform_records
from app.pipeline.validate import validate_rows


def test_text_whitespace_is_normalized():
    df = pd.DataFrame({"customer": ["  Acme   Corp  ", "Beta"]})
    columns = profile_columns(df)
    records = transform_records(validate_rows(df, columns), columns)

    assert records[0]["data"]["customer"] == "Acme Corp"
    assert records[1]["data"]["customer"] == "Beta"


def test_number_values_are_untouched():
    df = pd.DataFrame({"amount": [10.5, 20.0]})
    columns = profile_columns(df)
    records = transform_records(validate_rows(df, columns), columns)

    assert records[0]["data"]["amount"] == 10.5


def test_blank_text_becomes_none():
    df = pd.DataFrame({"customer": ["   ", "Beta"], "amount": [10, 20]})
    columns = profile_columns(df)
    records = transform_records(validate_rows(df, columns), columns)

    assert records[0]["data"]["customer"] is None
