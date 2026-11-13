"""Aggregate an import into the numbers and series a dashboard needs.

Aggregation runs on valid rows only. Flagged rows are excluded so a bad price
cannot silently distort a chart.
"""

import pandas as pd


def _id_like(name: str) -> bool:
    lowered = name.lower()
    return lowered == "id" or lowered.endswith("_id")


def _valid_dataframe(columns, rows) -> pd.DataFrame:
    names = [column["name"] for column in columns]
    data = [
        {name: row.data.get(name) for name in names}
        for row in rows
        if row.is_valid
    ]
    return pd.DataFrame(data, columns=names)


def build_dashboard(columns: list[dict], rows) -> dict:
    df = _valid_dataframe(columns, rows)
    numeric = [
        column["name"]
        for column in columns
        if column["type"] in {"integer", "number"} and not _id_like(column["name"])
    ]
    dates = [column["name"] for column in columns if column["type"] == "date"]

    dimensions = []
    for column in columns:
        name = column["name"]
        if column["type"] != "text" or _id_like(name) or name not in df:
            continue
        unique = df[name].dropna().nunique()
        if 2 <= unique <= 20:
            dimensions.append(name)

    dimension = dimensions[0] if dimensions else None
    date_column = dates[0] if dates else None
    metric = numeric[0] if numeric else None

    payload = {
        "row_count": len(df),
        "metric": metric,
        "dimension": dimension,
        "date_column": date_column,
        "metrics": [],
        "by_dimension": None,
        "by_date": None,
    }

    if df.empty:
        return payload

    for name in numeric:
        total = pd.to_numeric(df[name], errors="coerce").sum()
        payload["metrics"].append({"name": name, "total": float(total)})

    if dimension:
        if metric:
            series = (
                df.groupby(dimension, dropna=True)[metric]
                .apply(lambda values: pd.to_numeric(values, errors="coerce").sum())
                .sort_values(ascending=False)
            )
        else:
            series = df[dimension].value_counts().sort_values(ascending=False)
        payload["by_dimension"] = {
            "labels": [str(label) for label in series.index],
            "values": [float(value) for value in series.values],
            "metric": metric or "rows",
        }

    if date_column:
        dated = df.dropna(subset=[date_column]).copy()
        if not dated.empty:
            if metric:
                series = dated.groupby(date_column)[metric].apply(
                    lambda values: pd.to_numeric(values, errors="coerce").sum()
                )
            else:
                series = dated.groupby(date_column).size()
            series = series.sort_index()
            payload["by_date"] = {
                "labels": [str(label) for label in series.index],
                "values": [float(value) for value in series.values],
                "metric": metric or "rows",
            }

    return payload
