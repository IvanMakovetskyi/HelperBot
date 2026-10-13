import pytest

from helperbot.config import Settings


def test_existing_environment_keys_and_postgres_driver(monkeypatch):
    monkeypatch.setenv("TOKEN", "test-token")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:password@localhost/work?sslmode=require&channel_binding=require")
    monkeypatch.setenv("ADMIN", "12345")
    settings = Settings.from_env()
    assert settings.admin_id == 12345
    assert settings.database_url.startswith("postgresql+psycopg://")
    assert "sslmode=require" in settings.database_url


def test_admin_must_be_numeric(monkeypatch):
    monkeypatch.setenv("TOKEN", "test-token")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:password@localhost/work")
    monkeypatch.setenv("ADMIN", "not-a-number")
    with pytest.raises(ValueError, match="ADMIN"):
        Settings.from_env()
