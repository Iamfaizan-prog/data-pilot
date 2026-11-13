"""Small template helpers so field names read like language, not database columns."""

from datetime import datetime

UPPERCASE_WORDS = {"id", "sku", "url", "vat", "pdf", "csv", "api"}
TYPE_LABELS = {
    "integer": "whole number",
    "number": "decimal",
    "date": "date",
    "text": "text",
}


def pretty_column(name: str) -> str:
    words = str(name).replace("_", " ").split()
    if not words:
        return str(name)
    return " ".join(
        word.upper() if word.lower() in UPPERCASE_WORDS else word.capitalize()
        for word in words
    )


def sentence_case(text: str) -> str:
    words = str(text).split()
    if not words:
        return str(text)
    result = []
    for index, word in enumerate(words):
        if len(word) <= 4 and word.isupper():
            result.append(word)
        elif index == 0:
            result.append(word[:1].upper() + word[1:].lower())
        else:
            result.append(word.lower())
    return " ".join(result)


def lower_words(text: str) -> str:
    words = str(text).split()
    return " ".join(
        word if len(word) <= 4 and word.isupper() else word.lower()
        for word in words
    )


def pretty_type(value: str) -> str:
    return TYPE_LABELS.get(value, value)


def format_number(value) -> str:
    if value is None:
        return "—"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if number.is_integer():
        return f"{int(number):,}"
    return f"{number:,.2f}"


def format_date(value: str) -> str:
    try:
        parsed = datetime.strptime(str(value), "%Y-%m-%d")
    except ValueError:
        return str(value)
    return parsed.strftime("%d %b %Y")


def format_cell(value, column_type: str | None = None) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if column_type == "date":
        return format_date(value)
    if isinstance(value, (int, float)):
        return format_number(value)
    return str(value)


def format_timestamp(value, fmt: str = "%d %b %Y · %H:%M UTC") -> str:
    if not value:
        return "—"
    return value.strftime(fmt)
