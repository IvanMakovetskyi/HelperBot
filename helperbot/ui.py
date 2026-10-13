"""Short Russian copy and Telegram presentation helpers."""

from html import escape
from random import choice

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update


STATUS_LABELS = {
    "new": "🆕 Новая",
    "progress": "🛠 В работе",
    "done": "✅ Готово",
    "declined": "🚫 Не берём",
}

WELCOME = (
    "Привет! Здесь собираем процессы, которые едят время и делают вид, что так и надо. 🙃",
    "Привет! Расскажите, где работа решила стать квестом без награды. 🧩",
    "Привет! Если процесс крадёт часы, давайте поймаем его с поличным. 🕵️",
)

PROMPTS = {
    "name": "<b>1/4 · Имя</b>\nКак вас зовут?",
    "problem": "<b>2/4 · Проблема</b>\nКакой процесс отнимает время и что в нём не так? Пара конкретных предложений — идеально.",
    "time": "<b>3/4 · Время за неделю</b>\nСколько часов уходит? Например: <code>2</code> или <code>1,5</code>. Можно пропустить.",
    "optimization": "<b>4/4 · Идея</b>\nЧто, по-вашему, можно улучшить? Можно пропустить — магию пока не требуем. 🪄",
}


def hours_label(minutes: int | None) -> str:
    if minutes is None:
        return "не указано"
    return f"{minutes / 60:g} ч/нед"


def menu_keyboard(admin: bool = False, resume: str | None = None) -> InlineKeyboardMarkup:
    rows = []
    if resume:
        rows.append([InlineKeyboardButton("↩️ Продолжить черновик", callback_data=f"draft:resume:{resume}")])
    rows.extend([
        [InlineKeyboardButton("✍️ Рассказать о проблеме", callback_data="menu:new")],
        [InlineKeyboardButton("📂 Мои заявки", callback_data="menu:mine")],
        [InlineKeyboardButton("❔ Как это работает", callback_data="menu:help")],
    ])
    if admin:
        rows.append([InlineKeyboardButton("📥 Новые заявки", callback_data="admin:inbox")])
        rows.append([InlineKeyboardButton("📊 Сводка", callback_data="admin:stats")])
    return InlineKeyboardMarkup(rows)


def prompt_keyboard(draft: dict) -> InlineKeyboardMarkup:
    step = draft["step"].removeprefix("edit_")
    rows = []
    if step in {"time", "optimization"}:
        rows.append([InlineKeyboardButton("Пропустить →", callback_data=f"draft:skip:{draft['draft_id']}:{step}")])
    rows.append([InlineKeyboardButton("✖️ Отмена", callback_data=f"draft:cancel:{draft['draft_id']}")])
    return InlineKeyboardMarkup(rows)


def confirm_keyboard(draft_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Отправить", callback_data=f"draft:submit:{draft_id}")],
        [InlineKeyboardButton("✏️ Имя", callback_data=f"draft:edit:{draft_id}:name"), InlineKeyboardButton("✏️ Проблема", callback_data=f"draft:edit:{draft_id}:problem")],
        [InlineKeyboardButton("✏️ Время", callback_data=f"draft:edit:{draft_id}:time"), InlineKeyboardButton("✏️ Идея", callback_data=f"draft:edit:{draft_id}:optimization")],
        [InlineKeyboardButton("✖️ Отмена", callback_data=f"draft:cancel:{draft_id}")],
    ])


def admin_keyboard(idea_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛠 В работу", callback_data=f"admin:status:{idea_id}:progress"), InlineKeyboardButton("✅ Готово", callback_data=f"admin:status:{idea_id}:done")],
        [InlineKeyboardButton("🚫 Не берём", callback_data=f"admin:status:{idea_id}:declined")],
        [InlineKeyboardButton("↩️ Вернуть в новые", callback_data=f"admin:status:{idea_id}:new")],
    ])


def summary(draft: dict) -> str:
    return (
        "<b>Всё верно?</b> 👀\n\n"
        f"<b>Имя:</b> {escape(draft['name'] or '—')}\n"
        f"<b>Проблема:</b> {escape(draft['problem'] or '—')}\n"
        f"<b>Время:</b> {hours_label(draft['weekly_minutes'])}\n"
        f"<b>Можно улучшить:</b> {escape(draft['optimization'] or 'не указано')}"
    )


def idea_card(idea: dict, *, admin: bool = False) -> str:
    header = f"<b>Заявка #{idea['id']}</b> · {STATUS_LABELS[idea['status']]}"
    author = f"\n<b>Автор:</b> {escape(idea['name'])}"
    if admin and idea.get("username"):
        author += f" (@{escape(idea['username'])})"
    return (
        f"{header}{author}\n"
        f"<b>Проблема:</b> {escape(idea['problem'])}\n"
        f"<b>Время:</b> {hours_label(idea['weekly_minutes'])}\n"
        f"<b>Идея:</b> {escape(idea['optimization'] or 'не указана')}"
    )


async def respond(update: Update, text: str, markup: InlineKeyboardMarkup | None = None) -> None:
    """Edit a tapped bot message or send a new one after a user message."""
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode="HTML", reply_markup=markup)
    elif update.effective_message:
        await update.effective_message.reply_text(text, parse_mode="HTML", reply_markup=markup)


def welcome() -> str:
    return choice(WELCOME)
