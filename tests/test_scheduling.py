from datetime import datetime, timezone
from email import message_from_bytes
from email.header import decode_header, make_header

from app.reports.emailer import send_report_email
from app.scheduling import advance_next_run, compute_next_run


def test_next_run_is_today_when_hour_is_ahead():
    now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    assert compute_next_run("daily", 14, now) == datetime(
        2026, 1, 1, 14, 0, tzinfo=timezone.utc
    )


def test_next_run_rolls_to_tomorrow_when_hour_has_passed():
    now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    assert compute_next_run("daily", 8, now) == datetime(
        2026, 1, 2, 8, 0, tzinfo=timezone.utc
    )


def test_advance_daily_and_weekly():
    now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    current = datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc)

    assert advance_next_run(current, "daily", now) == datetime(
        2026, 1, 2, 8, 0, tzinfo=timezone.utc
    )
    assert advance_next_run(current, "weekly", now) == datetime(
        2026, 1, 8, 8, 0, tzinfo=timezone.utc
    )


def test_email_without_smtp_writes_eml_file(tmp_path):
    config = {
        "SMTP_HOST": None,
        "SMTP_FROM": "reports@example.com",
        "OUTBOX_FOLDER": tmp_path,
    }

    destination = send_report_email(
        config,
        ["client@example.com"],
        "DataPilot report: sales.csv",
        "Attached.",
        "sales_datapilot.pdf",
        b"%PDF-1.4 fake",
    )

    path = tmp_path / destination.split("/")[-1]
    assert path.exists()

    message = message_from_bytes(path.read_bytes())
    assert str(make_header(decode_header(message["To"]))) == "client@example.com"
    assert "DataPilot report" in str(message["Subject"])
    assert message.get_content_type() == "multipart/mixed"
