"""Small async persistence layer. Drafts survive process restarts."""

from datetime import datetime, timezone
from secrets import token_urlsafe

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    delete,
    func,
    insert,
    select,
    update,
)
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


metadata = MetaData()

drafts = Table(
    "helperbot_drafts",
    metadata,
    Column("user_id", BigInteger, primary_key=True),
    Column("draft_id", String(16), nullable=False),
    Column("step", String(32), nullable=False),
    Column("name", String(80)),
    Column("problem", Text),
    Column("weekly_minutes", Integer),
    Column("optimization", Text),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

ideas = Table(
    "helperbot_ideas",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_id", BigInteger, nullable=False, index=True),
    Column("username", String(64)),
    Column("name", String(80), nullable=False),
    Column("problem", Text, nullable=False),
    Column("weekly_minutes", Integer),
    Column("optimization", Text),
    Column("status", String(16), nullable=False, index=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

STEPS = {"name", "problem", "time", "optimization", "confirm", "edit_name", "edit_problem", "edit_time", "edit_optimization"}
STATUSES = {"new", "progress", "done", "declined"}


class Storage:
    def __init__(self, database_url: str):
        self.engine: AsyncEngine = create_async_engine(database_url, pool_pre_ping=True)

    async def initialize(self) -> None:
        async with self.engine.begin() as connection:
            await connection.run_sync(metadata.create_all)

    async def close(self) -> None:
        await self.engine.dispose()

    async def get_draft(self, user_id: int) -> dict | None:
        async with self.engine.connect() as connection:
            result = await connection.execute(select(drafts).where(drafts.c.user_id == user_id))
            row = result.mappings().first()
            return dict(row) if row else None

    async def save_draft(self, user_id: int, *, step: str, **fields: object) -> None:
        if step not in STEPS or not set(fields) <= {"name", "problem", "weekly_minutes", "optimization"}:
            raise ValueError("Invalid draft fields")
        now = datetime.now(timezone.utc)
        async with self.engine.begin() as connection:
            existing = await connection.execute(select(drafts.c.user_id).where(drafts.c.user_id == user_id))
            if existing.first():
                await connection.execute(
                    update(drafts).where(drafts.c.user_id == user_id).values(step=step, updated_at=now, **fields)
                )
            else:
                await connection.execute(insert(drafts).values(user_id=user_id, draft_id=token_urlsafe(8), step=step, updated_at=now, **fields))

    async def delete_draft(self, user_id: int) -> None:
        async with self.engine.begin() as connection:
            await connection.execute(delete(drafts).where(drafts.c.user_id == user_id))

    async def submit_draft(self, user_id: int, username: str | None) -> dict | None:
        now = datetime.now(timezone.utc)
        async with self.engine.begin() as connection:
            result = await connection.execute(select(drafts).where(drafts.c.user_id == user_id).with_for_update())
            draft = result.mappings().first()
            if not draft or draft["step"] != "confirm" or not draft["name"] or not draft["problem"]:
                return None
            values = {
                "user_id": user_id,
                "username": username,
                "name": draft["name"],
                "problem": draft["problem"],
                "weekly_minutes": draft["weekly_minutes"],
                "optimization": draft["optimization"],
                "status": "new",
                "created_at": now,
                "updated_at": now,
            }
            inserted = await connection.execute(insert(ideas).values(**values).returning(ideas.c.id))
            idea_id = inserted.scalar_one()
            await connection.execute(delete(drafts).where(drafts.c.user_id == user_id))
            return {"id": idea_id, **values}

    async def get_idea(self, idea_id: int) -> dict | None:
        async with self.engine.connect() as connection:
            result = await connection.execute(select(ideas).where(ideas.c.id == idea_id))
            row = result.mappings().first()
            return dict(row) if row else None

    async def list_user_ideas(self, user_id: int, limit: int = 10) -> list[dict]:
        async with self.engine.connect() as connection:
            result = await connection.execute(
                select(ideas).where(ideas.c.user_id == user_id).order_by(ideas.c.id.desc()).limit(limit)
            )
            return [dict(row) for row in result.mappings()]

    async def list_new_ideas(self, limit: int = 10) -> list[dict]:
        async with self.engine.connect() as connection:
            result = await connection.execute(
                select(ideas).where(ideas.c.status == "new").order_by(ideas.c.id.asc()).limit(limit)
            )
            return [dict(row) for row in result.mappings()]

    async def status_counts(self) -> dict[str, int]:
        async with self.engine.connect() as connection:
            result = await connection.execute(select(ideas.c.status, func.count()).group_by(ideas.c.status))
            return {status: count for status, count in result}

    async def set_status(self, idea_id: int, status: str) -> tuple[dict | None, bool]:
        if status not in STATUSES:
            raise ValueError("Invalid status")
        async with self.engine.begin() as connection:
            result = await connection.execute(select(ideas).where(ideas.c.id == idea_id).with_for_update())
            current = result.mappings().first()
            if not current:
                return None, False
            if current["status"] == status:
                return dict(current), False
            now = datetime.now(timezone.utc)
            await connection.execute(update(ideas).where(ideas.c.id == idea_id).values(status=status, updated_at=now))
            return {**dict(current), "status": status, "updated_at": now}, True
