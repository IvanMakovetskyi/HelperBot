from types import SimpleNamespace

import pytest_asyncio

from helperbot.storage import Storage


class FakeBot:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id, text, **kwargs):
        self.sent.append((chat_id, text, kwargs))


class FakeMessage:
    def __init__(self, text=""):
        self.text = text
        self.sent = []

    async def reply_text(self, text, **kwargs):
        self.sent.append((text, kwargs))


class FakeQuery:
    def __init__(self, data):
        self.data = data
        self.answered = False
        self.edits = []

    async def answer(self, *args, **kwargs):
        self.answered = True

    async def edit_message_text(self, text, **kwargs):
        self.edits.append((text, kwargs))


def fake_update(*, user_id=10, text="", data=None):
    message = FakeMessage(text)
    query = FakeQuery(data) if data is not None else None
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=user_id, username="tester"),
        effective_chat=SimpleNamespace(id=user_id, type="private"),
        effective_message=message,
        callback_query=query,
    )


def fake_context(storage, *, admin_id=99):
    bot = FakeBot()
    return SimpleNamespace(application=SimpleNamespace(bot_data={"storage": storage, "admin_id": admin_id}), bot=bot)


@pytest_asyncio.fixture
async def storage(tmp_path):
    store = Storage(f"sqlite+aiosqlite:///{(tmp_path / 'test.db').as_posix()}")
    await store.initialize()
    yield store
    await store.close()
