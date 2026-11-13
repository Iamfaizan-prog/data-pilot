"""Send report emails over SMTP, or write .eml files when SMTP is not configured."""

import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path


def attachment_name(filename: str) -> str:
    return f"{Path(filename).stem}_datapilot.pdf"


def report_body(import_record) -> str:
    return (
        f"Scheduled report for {import_record.filename}.\n\n"
        f"Rows: {import_record.row_count}\n"
        f"Clean rows: {import_record.row_count - import_record.flagged_count}\n"
        f"Flagged rows: {import_record.flagged_count}\n\n"
        "The PDF report is attached.\n"
    )


def send_report_email(
    config,
    recipients: list[str],
    subject: str,
    body: str,
    attachment_name: str,
    attachment_bytes: bytes,
) -> str:
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = config.get("SMTP_FROM") or "datapilot@localhost"
    message["To"] = ", ".join(recipients)
    message.set_content(body)
    message.add_attachment(
        attachment_bytes,
        maintype="application",
        subtype="pdf",
        filename=attachment_name,
    )

    host = config.get("SMTP_HOST")
    if not host:
        outbox = Path(config["OUTBOX_FOLDER"])
        outbox.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
        path = outbox / f"{stamp}.eml"
        path.write_bytes(message.as_bytes())
        return str(path)

    with smtplib.SMTP(host, int(config.get("SMTP_PORT", 587)), timeout=20) as server:
        if config.get("SMTP_USE_TLS", True):
            server.starttls()
        user = config.get("SMTP_USER")
        if user:
            server.login(user, config.get("SMTP_PASSWORD", ""))
        server.send_message(message)
    return "smtp"
