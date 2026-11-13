from datetime import datetime, timezone

from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB

from .extensions import db

# JSONB on PostgreSQL, plain JSON in tests on SQLite.
JSON_VALUE = JSON().with_variant(JSONB(), "postgresql")


def utcnow():
    return datetime.now(timezone.utc)


class Import(db.Model):
    __tablename__ = "imports"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(32), nullable=False, index=True)
    filename = db.Column(db.String(255), nullable=False)
    stored_path = db.Column(db.String(500), nullable=False)
    uploaded_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    status = db.Column(db.String(20), default="processed", nullable=False)
    row_count = db.Column(db.Integer, default=0, nullable=False)
    flagged_count = db.Column(db.Integer, default=0, nullable=False)
    # Column profile inferred from the file: [{"name": ..., "type": ...}, ...]
    columns = db.Column(JSON_VALUE, default=list, nullable=False)

    rows = db.relationship(
        "ImportRow",
        back_populates="import_record",
        cascade="all, delete-orphan",
        order_by="ImportRow.row_number",
    )
    schedule = db.relationship(
        "ReportSchedule",
        back_populates="import_record",
        cascade="all, delete-orphan",
        uselist=False,
    )


class ImportRow(db.Model):
    __tablename__ = "import_rows"

    id = db.Column(db.Integer, primary_key=True)
    import_id = db.Column(
        db.Integer, db.ForeignKey("imports.id", ondelete="CASCADE"), nullable=False
    )
    # 1-based position among data rows, not counting the header.
    row_number = db.Column(db.Integer, nullable=False)
    data = db.Column(JSON_VALUE, nullable=False)
    is_valid = db.Column(db.Boolean, default=True, nullable=False)
    issues = db.Column(JSON_VALUE, default=list, nullable=False)

    import_record = db.relationship("Import", back_populates="rows")


class ReportSchedule(db.Model):
    __tablename__ = "report_schedules"

    id = db.Column(db.Integer, primary_key=True)
    import_id = db.Column(
        db.Integer, db.ForeignKey("imports.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    recipients = db.Column(db.String(1000), nullable=False)
    frequency = db.Column(db.String(10), default="daily", nullable=False)
    hour = db.Column(db.Integer, default=8, nullable=False)
    enabled = db.Column(db.Boolean, default=True, nullable=False)
    next_run_at = db.Column(db.DateTime(timezone=True), nullable=False)
    last_sent_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    import_record = db.relationship("Import", back_populates="schedule")
