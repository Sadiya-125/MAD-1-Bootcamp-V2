import pytest

from app import create_app
from models import db


class TestConfig:
    TESTING = True
    SECRET_KEY = "test"
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    WTF_CSRF_ENABLED = False


@pytest.fixture
def app():
    app = create_app(TestConfig)

    app.test_cli_runner().invoke(args=["seed"])
    yield app
    with app.app_context():
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def login(client):
    def do_login(username, password="password123"):
        return client.post("/login", data={"identifier": username, "password": password})

    return do_login