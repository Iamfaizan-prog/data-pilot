from pathlib import Path

import pandas as pd


class ExtractionError(ValueError):
    pass


def read_table(path: str | Path) -> pd.DataFrame:
    """Read a CSV or Excel file into a DataFrame.

    CSV encoding is tried in order because client exports are rarely plain UTF-8.
    """
    path = Path(path)
    suffix = path.suffix.lower()

    if suffix == ".csv":
        last_error = None
        for encoding in ("utf-8-sig", "utf-8", "latin-1"):
            try:
                return pd.read_csv(path, encoding=encoding)
            except UnicodeDecodeError as exc:
                last_error = exc
            except pd.errors.EmptyDataError as exc:
                raise ExtractionError("The file has no data.") from exc
        raise ExtractionError(f"Could not decode CSV: {last_error}")

    if suffix in {".xlsx", ".xls"}:
        try:
            return pd.read_excel(path)
        except Exception as exc:  # openpyxl/xlrd raise several types
            raise ExtractionError(f"Could not read spreadsheet: {exc}") from exc

    raise ExtractionError(f"Unsupported file type: {suffix or 'unknown'}")
