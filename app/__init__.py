from uuid import uuid4

from flask import Flask, render_template, session

from .config import Config
from .extensions import db
from .presentation import (
    format_cell,
    format_number,
    format_timestamp,
    lower_words,
    pretty_column,
    pretty_type,
    sentence_case,
)


def create_app(config_object=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if config_object:
        app.config.update(config_object)

    if app.config.get("TESTING"):
        app.config["SESSION_COOKIE_SECURE"] = False

    if not app.config.get("SECRET_KEY"):
        if app.config.get("TESTING"):
            app.config["SECRET_KEY"] = "testing-only-secret"
        else:
            raise RuntimeError(
                "SECRET_KEY must be set in the environment before starting DataPilot."
            )

    db.init_app(app)

    from .routes import bp

    app.register_blueprint(bp)

    app.jinja_env.filters["pretty"] = pretty_column
    app.jinja_env.filters["pretty_type"] = pretty_type
    app.jinja_env.filters["sentence"] = sentence_case
    app.jinja_env.filters["lower_words"] = lower_words
    app.jinja_env.filters["num"] = format_number
    app.jinja_env.filters["cell"] = format_cell
    app.jinja_env.filters["stamp_time"] = format_timestamp

    @app.before_request
    def assign_session():
        if "sid" not in session:
            session["sid"] = uuid4().hex
            session.permanent = True

    @app.errorhandler(413)
    def file_too_large(error):
        return render_template("413.html"), 413

    with app.app_context():
        # create_all only creates missing tables. Add Alembic migrations before real use.
        db.create_all()

    if app.config.get("ENABLE_SCHEDULER") and not app.config.get("TESTING"):
        from .scheduler import start_scheduler

        start_scheduler(app)

    return app
