import io
import re

import pytest

from app import create_app
from app.extensions import db


@pytest.fixture
def app(tmp_path):
    application = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'test.db'}",
            "UPLOAD_FOLDER": tmp_path / "uploads",
            "ENABLE_SCHEDULER": False,
        }
    )
    yield application
    with application.app_context():
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def _import_sample(client):
    response = client.post("/imports/sample")
    assert response.status_code == 302
    match = re.search(r"/imports/(\d+)", response.headers["Location"])
    assert match
    return int(match.group(1))


def test_other_session_gets_404_on_someone_elses_import(client):
    client.get("/")
    import_id = _import_sample(client)

    stranger = client.application.test_client()
    stranger.get("/")

    assert client.get(f"/imports/{import_id}").status_code == 200
    assert stranger.get(f"/imports/{import_id}").status_code == 404
    assert stranger.get(f"/imports/{import_id}/dashboard").status_code == 404
    assert stranger.get(f"/imports/{import_id}/export.xlsx").status_code == 404


def test_disallowed_extension_is_rejected(client):
    client.get("/")
    response = client.post(
        "/imports",
        data={"file": (io.BytesIO(b"a,b\n1,2\n"), "notes.txt")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Only .csv, .xlsx, and .xls" in response.data


def test_oversized_upload_returns_413(app, client):
    app.config["MAX_CONTENT_LENGTH"] = 200
    client.get("/")

    response = client.post(
        "/imports",
        data={"file": (io.BytesIO(b"a,b\n" + b"1,2\n" * 200), "big.csv")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 413
    assert b"File too large" in response.data


def test_session_only_lists_own_imports(client):
    client.get("/")
    _import_sample(client)

    stranger = client.application.test_client()
    response = stranger.get("/")

    assert b"Recent imports" in response.data
    assert b"No imports yet" in response.data
