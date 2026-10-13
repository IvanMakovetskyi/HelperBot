"""Configuration loaded from the existing .env file or process environment."""

from dataclasses import dataclass
import os

from dotenv import load_dotenv
from sqlalchemy.engine import make_url


@dataclass(frozen=True)
class Settings:
    token: str
    database_url: str
    admin_id: int

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        token = os.getenv("TOKEN") or os.getenv("BOT_TOKEN")
        database_url = os.getenv("DATABASE_URL")
        admin = os.getenv("ADMIN") or os.getenv("ADMIN_ID")
        missing = [key for key, value in (("TOKEN", token), ("DATABASE_URL", database_url), ("ADMIN", admin)) if not value]
        if missing:
            raise ValueError(f"Не заданы переменные окружения: {', '.join(missing)}")
        try:
            admin_id = int(admin)
        except ValueError as exc:
            raise ValueError("ADMIN должен быть числовым Telegram ID") from exc
        if admin_id <= 0:
            raise ValueError("ADMIN должен быть положительным Telegram ID")
        url = make_url(database_url)
        if url.drivername in {"postgres", "postgresql"}:
            url = url.set(drivername="postgresql+psycopg")
        if url.drivername not in {"postgresql+psycopg", "sqlite+aiosqlite"}:
            raise ValueError("DATABASE_URL должен указывать на PostgreSQL")
        return cls(token=token, database_url=url.render_as_string(hide_password=False), admin_id=admin_id)
