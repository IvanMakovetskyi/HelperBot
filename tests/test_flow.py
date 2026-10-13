import pytest

from helperbot import admin, user
from helperbot.ui import summary
from conftest import fake_context, fake_update


def test_hours_and_escaping():
    assert user.parse_hours("1,5") == 90
    assert user.parse_hours("2") == 120
    assert user.parse_hours("0") is None
    assert user.parse_hours("169") is None
    assert user.parse_hours("abc") is None
    rendered = summary({"name": "<Аня>", "problem": "A & B", "weekly_minutes": None, "optimization": None})
    assert "&lt;Аня&gt;" in rendered
    assert "A &amp; B" in rendered


@pytest.mark.asyncio
async def test_submission_edit_and_admin_status(storage):
    context = fake_context(storage)
    await user.new(fake_update(), context)
    await user.on_text(fake_update(text="Аня"), context)
    await user.on_text(fake_update(text="Каждую пятницу переношу данные вручную"), context)
    draft = await storage.get_draft(10)
    skip = fake_update(data=f"draft:skip:{draft['draft_id']}:time")
    await user.on_callback(skip, context)
    assert skip.callback_query.answered
    await user.on_text(fake_update(text="Автоматически выгружать отчёт"), context)
    draft = await storage.get_draft(10)
    assert draft["step"] == "confirm"
    await user.on_callback(fake_update(data=f"draft:edit:{draft['draft_id']}:name"), context)
    await user.on_text(fake_update(text="Анна"), context)
    assert (await storage.get_draft(10))["step"] == "confirm"
    sent = fake_update(data=f"draft:submit:{draft['draft_id']}")
    await user.on_callback(sent, context)
    assert sent.callback_query.answered
    assert await storage.get_draft(10) is None
    rows = await storage.list_user_ideas(10)
    assert len(rows) == 1
    assert rows[0]["name"] == "Анна"
    assert rows[0]["weekly_minutes"] is None
    assert context.bot.sent[0][0] == 99
    detail = fake_update(data=f"menu:idea:{rows[0]['id']}")
    await user.on_callback(detail, context)
    assert "Автоматически выгружать отчёт" in detail.callback_query.edits[0][0]
    other_user = fake_update(user_id=11, data=f"menu:idea:{rows[0]['id']}")
    await user.on_callback(other_user, context)
    assert "недоступна" in other_user.callback_query.edits[0][0]
    assert await storage.submit_draft(10, "tester") is None

    admin_context = fake_context(storage)
    unauthorized = fake_update(user_id=11, data=f"admin:status:{rows[0]['id']}:done")
    await admin.on_callback(unauthorized, admin_context)
    assert (await storage.get_idea(rows[0]["id"]))["status"] == "new"
    change = fake_update(user_id=99, data=f"admin:status:{rows[0]['id']}:progress")
    await admin.on_callback(change, admin_context)
    assert change.callback_query.answered
    assert (await storage.get_idea(rows[0]["id"]))["status"] == "progress"
    assert admin_context.bot.sent[0][0] == 10
    assert (await storage.status_counts()) == {"progress": 1}


@pytest.mark.asyncio
async def test_old_buttons_cannot_submit_replaced_draft(storage):
    context = fake_context(storage)
    await user.new(fake_update(), context)
    old_id = (await storage.get_draft(10))["draft_id"]
    await user.new(fake_update(), context)
    current = await storage.get_draft(10)
    assert current["draft_id"] != old_id
    await user.on_callback(fake_update(data=f"draft:submit:{old_id}"), context)
    assert await storage.list_user_ideas(10) == []
    assert (await storage.get_draft(10))["draft_id"] == current["draft_id"]
