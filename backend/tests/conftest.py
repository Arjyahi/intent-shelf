from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from app.core.settings import get_settings
from app.db.session import get_session_factory, reset_db_session_factory
from app.main import app


@pytest.fixture()
def sqlite_database_url(tmp_path, monkeypatch):
    db_path = tmp_path / "runtime_state.db"
    url = f"sqlite+pysqlite:///{db_path.as_posix()}"

    monkeypatch.setenv("INTENTSHELF_DATABASE_URL", url)
    monkeypatch.setenv("DATABASE_URL", url)
    get_settings.cache_clear()
    reset_db_session_factory()

    yield url

    reset_db_session_factory()
    get_settings.cache_clear()


@pytest.fixture()
def migrated_database(sqlite_database_url):
    backend_dir = Path(__file__).resolve().parents[1]
    config = Config(str(backend_dir / "alembic.ini"))
    config.set_main_option("script_location", str(backend_dir / "alembic"))
    config.set_main_option("sqlalchemy.url", sqlite_database_url)
    command.upgrade(config, "head")
    return sqlite_database_url


@pytest.fixture()
def db_session(migrated_database):
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(migrated_database):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def configured_runtime_database(migrated_database):
    yield
