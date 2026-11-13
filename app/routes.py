import re
import shutil
import uuid
from datetime import timedelta
from pathlib import Path

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from werkzeug.utils import secure_filename

from .extensions import db
from .models import Import, ImportRow, ReportSchedule, utcnow
from .pipeline import ExtractionError, profile_columns, read_table, transform_records, validate_rows
from .reports import build_dashboard, build_excel, build_pdf
from .reports.emailer import attachment_name, report_body, send_report_email
from .scheduling import advance_next_run, compute_next_run

bp = Blueprint("main", __name__)

# v1 identifies business keys by common column names. A per-client mapping will
# replace this heuristic later.
UNIQUE_KEY_CANDIDATES = ("order_id", "invoice_id", "order_number", "invoice_number")

MAX_ROWS = 20_000
MAX_COLUMNS = 100
MAX_SCHEDULES_PER_SESSION = 3
RETENTION = timedelta(hours=24)
EMAIL_PATTERN = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


def _unique_columns(columns: list[dict]) -> list[str]:
    names = {column["name"].lower(): column["name"] for column in columns}
    return [names[candidate] for candidate in UNIQUE_KEY_CANDIDATES if candidate in names]


def _current_sid() -> str | None:
    return session.get("sid")


def _get_import_or_404(import_id: int) -> Import:
    return Import.query.filter_by(
        id=import_id, session_id=_current_sid()
    ).first_or_404()


def _cleanup_expired_imports() -> None:
    cutoff = utcnow() - RETENTION
    expired = Import.query.filter(Import.uploaded_at < cutoff).all()
    if not expired:
        return

    paths = [record.stored_path for record in expired]
    for record in expired:
        db.session.delete(record)
    db.session.commit()

    for stored_path in paths:
        if stored_path:
            Path(stored_path).unlink(missing_ok=True)


@bp.app_context_processor
def navigation_context():
    sid = _current_sid()
    latest = (
        Import.query.filter_by(session_id=sid)
        .order_by(Import.uploaded_at.desc())
        .first()
    )
    return {
        "nav_latest_import": latest,
        "nav_import_count": Import.query.filter_by(session_id=sid).count(),
        "smtp_configured": bool(current_app.config.get("SMTP_HOST")),
    }


def _allowed(filename: str) -> bool:
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in current_app.config["ALLOWED_EXTENSIONS"]
    )


@bp.get("/health")
def health():
    return "ok"


@bp.get("/")
def index():
    imports = (
        Import.query.filter_by(session_id=_current_sid())
        .order_by(Import.uploaded_at.desc())
        .all()
    )
    return render_template("index.html", imports=imports)


def _store_import(stored_path: Path, original_name: str):
    try:
        df = read_table(stored_path)
        if len(df) > MAX_ROWS or len(df.columns) > MAX_COLUMNS:
            raise ExtractionError(
                f"This file has {len(df):,} rows and {len(df.columns):,} columns. "
                f"The demo limit is {MAX_ROWS:,} rows and {MAX_COLUMNS} columns."
            )
        columns = profile_columns(df)
        records = validate_rows(df, columns, unique_columns=_unique_columns(columns))
        records = transform_records(records, columns)
    except ExtractionError as exc:
        stored_path.unlink(missing_ok=True)
        flash(str(exc), "error")
        return redirect(url_for("main.index"))

    import_record = Import(
        session_id=_current_sid(),
        filename=original_name,
        stored_path=str(stored_path),
        row_count=len(records),
        flagged_count=sum(1 for record in records if not record["is_valid"]),
        columns=columns,
    )
    db.session.add(import_record)
    db.session.flush()  # assign import_record.id without committing yet

    db.session.add_all(
        [
            ImportRow(
                import_id=import_record.id,
                row_number=record["row_number"],
                data=record["data"],
                is_valid=record["is_valid"],
                issues=record["issues"],
            )
            for record in records
        ]
    )
    db.session.commit()

    return redirect(url_for("main.import_detail", import_id=import_record.id))


@bp.post("/imports")
def upload():
    _cleanup_expired_imports()

    file = request.files.get("file")
    if file is None or file.filename == "":
        flash("Choose a CSV or Excel file first.", "error")
        return redirect(url_for("main.index"))

    if not _allowed(file.filename):
        flash("Only .csv, .xlsx, and .xls files are supported.", "error")
        return redirect(url_for("main.index"))

    upload_dir = Path(current_app.config["UPLOAD_FOLDER"])
    upload_dir.mkdir(parents=True, exist_ok=True)

    original_name = secure_filename(file.filename) or f"import{Path(file.filename).suffix.lower()}"
    suffix = Path(file.filename).suffix.lower()
    stored_path = upload_dir / f"{uuid.uuid4().hex}{suffix}"
    file.save(stored_path)

    return _store_import(stored_path, original_name)


@bp.post("/imports/sample")
def import_sample():
    _cleanup_expired_imports()

    sample = Path(current_app.root_path).parent / "sample_data" / "messy_sales.csv"
    if not sample.exists():
        flash("The sample file is not available.", "error")
        return redirect(url_for("main.index"))

    upload_dir = Path(current_app.config["UPLOAD_FOLDER"])
    upload_dir.mkdir(parents=True, exist_ok=True)
    stored_path = upload_dir / f"{uuid.uuid4().hex}.csv"
    shutil.copyfile(sample, stored_path)

    return _store_import(stored_path, sample.name)


@bp.get("/imports/<int:import_id>")
def import_detail(import_id: int):
    import_record = _get_import_or_404(import_id)
    return render_template("import_detail.html", import_record=import_record)


@bp.get("/imports/<int:import_id>/export.xlsx")
def export_excel(import_id: int):
    import_record = _get_import_or_404(import_id)
    stream = build_excel(import_record.filename, import_record.columns, import_record.rows)
    download_name = f"{Path(import_record.filename).stem}_datapilot.xlsx"
    return send_file(
        stream,
        as_attachment=True,
        download_name=download_name,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@bp.get("/imports/<int:import_id>/export.pdf")
def export_pdf(import_id: int):
    import_record = _get_import_or_404(import_id)
    stream = build_pdf(import_record.filename, import_record.columns, import_record.rows)
    download_name = f"{Path(import_record.filename).stem}_datapilot.pdf"
    return send_file(
        stream,
        as_attachment=True,
        download_name=download_name,
        mimetype="application/pdf",
    )


@bp.get("/imports/<int:import_id>/dashboard")
def dashboard(import_id: int):
    import_record = _get_import_or_404(import_id)
    data = build_dashboard(import_record.columns, import_record.rows)
    return render_template(
        "dashboard.html", import_record=import_record, dashboard=data
    )


@bp.post("/imports/<int:import_id>/delete")
def delete_import(import_id: int):
    import_record = _get_import_or_404(import_id)
    stored_path = Path(import_record.stored_path)
    db.session.delete(import_record)
    db.session.commit()
    stored_path.unlink(missing_ok=True)

    flash("Import deleted.", "message")
    return redirect(url_for("main.index"))


def _parse_recipients(raw: str) -> list[str]:
    return [
        value.strip()
        for value in raw.replace(";", ",").split(",")
        if value.strip()
    ]


@bp.post("/imports/<int:import_id>/schedule")
def save_schedule(import_id: int):
    import_record = _get_import_or_404(import_id)
    recipients = _parse_recipients(request.form.get("recipients", ""))
    frequency = request.form.get("frequency", "daily")

    if len(recipients) != 1:
        flash("Add one recipient per schedule.", "error")
        return redirect(url_for("main.import_detail", import_id=import_id))

    if not EMAIL_PATTERN.fullmatch(recipients[0]):
        flash("Enter a valid email address.", "error")
        return redirect(url_for("main.import_detail", import_id=import_id))

    if frequency not in {"daily", "weekly"}:
        flash("Choose daily or weekly.", "error")
        return redirect(url_for("main.import_detail", import_id=import_id))

    try:
        hour = int(request.form.get("hour", "8"))
    except ValueError:
        hour = -1
    if not 0 <= hour <= 23:
        flash("Hour must be between 0 and 23 (UTC).", "error")
        return redirect(url_for("main.import_detail", import_id=import_id))

    schedule = import_record.schedule
    if schedule is None:
        count = (
            ReportSchedule.query.join(Import)
            .filter(Import.session_id == _current_sid())
            .count()
        )
        if count >= MAX_SCHEDULES_PER_SESSION:
            flash(
                f"This demo allows up to {MAX_SCHEDULES_PER_SESSION} email schedules per session.",
                "error",
            )
            return redirect(url_for("main.import_detail", import_id=import_id))
        schedule = ReportSchedule(import_id=import_record.id)
        db.session.add(schedule)

    schedule.recipients = recipients[0]
    schedule.frequency = frequency
    schedule.hour = hour
    schedule.enabled = request.form.get("enabled") == "on"
    schedule.next_run_at = compute_next_run(frequency, hour)
    db.session.commit()

    flash("Email schedule saved.", "message")
    return redirect(url_for("main.import_detail", import_id=import_id))


@bp.post("/imports/<int:import_id>/send")
def send_now(import_id: int):
    import_record = _get_import_or_404(import_id)
    schedule = import_record.schedule
    if schedule is None:
        flash("Set up an email schedule first.", "error")
        return redirect(url_for("main.import_detail", import_id=import_id))

    recipients = _parse_recipients(schedule.recipients)
    stream = build_pdf(import_record.filename, import_record.columns, import_record.rows)
    try:
        destination = send_report_email(
            current_app.config,
            recipients,
            f"DataPilot report: {import_record.filename}",
            report_body(import_record),
            attachment_name(import_record.filename),
            stream.read(),
        )
    except Exception as exc:
        current_app.logger.exception("Manual report send failed")
        flash(f"Could not send email: {exc}", "error")
        return redirect(url_for("main.import_detail", import_id=import_id))

    now = utcnow()
    schedule.last_sent_at = now
    schedule.next_run_at = advance_next_run(schedule.next_run_at, schedule.frequency, now)
    db.session.commit()

    if destination == "smtp":
        flash("Report sent by email.", "message")
    else:
        flash(f"SMTP is not configured, so the email was written to {destination}.", "message")
    return redirect(url_for("main.import_detail", import_id=import_id))
