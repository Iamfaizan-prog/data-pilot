"""In-process scheduler. One job checks due report schedules every minute."""

import os

from apscheduler.schedulers.background import BackgroundScheduler

_scheduler = None


def _send_due(app):
    from .extensions import db
    from .models import ReportSchedule
    from .reports.emailer import attachment_name, report_body, send_report_email
    from .reports.pdf import build_pdf
    from .scheduling import advance_next_run

    with app.app_context():
        due = ReportSchedule.query.filter(
            ReportSchedule.enabled.is_(True),
            ReportSchedule.next_run_at <= db.func.now(),
        ).all()

        for schedule in due:
            import_record = schedule.import_record
            stream = build_pdf(
                import_record.filename, import_record.columns, import_record.rows
            )
            recipients = [
                value.strip()
                for value in schedule.recipients.split(",")
                if value.strip()
            ]
            try:
                destination = send_report_email(
                    app.config,
                    recipients,
                    f"DataPilot report: {import_record.filename}",
                    report_body(import_record),
                    attachment_name(import_record.filename),
                    stream.read(),
                )
                schedule.last_sent_at = db.func.now()
                schedule.next_run_at = advance_next_run(
                    schedule.next_run_at, schedule.frequency
                )
                app.logger.info("Sent scheduled report to %s", destination)
            except Exception:
                app.logger.exception("Scheduled report failed for %s", schedule.id)

        db.session.commit()


def start_scheduler(app):
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    # Flask's debug reloader starts the app twice; only run the job in the child.
    if os.environ.get("FLASK_DEBUG") == "1" and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        return None

    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(
        _send_due,
        "interval",
        seconds=60,
        args=[app],
        id="send-due-reports",
        replace_existing=True,
    )
    _scheduler.start()
    return _scheduler
