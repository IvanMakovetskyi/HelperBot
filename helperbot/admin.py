"""Admin inbox, status actions and concise statistics."""

from html import escape
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from .ui import STATUS_LABELS, admin_keyboard, idea_card, respond
from .user import is_private, storage


logger = logging.getLogger(__name__)


def allowed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    return is_private(update) and update.effective_user.id == context.application.bot_data["admin_id"]


def inbox_keyboard(rows: list[dict]) -> InlineKeyboardMarkup:
    buttons = []
    for idea in rows:
        preview = idea["problem"].replace("\n", " ")[:42]
        buttons.append([InlineKeyboardButton(f"#{idea['id']} · {preview}", callback_data=f"admin:view:{idea['id']}")])
    buttons.append([InlineKeyboardButton("🔄 Обновить", callback_data="admin:inbox")])
    return InlineKeyboardMarkup(buttons)


def card_keyboard(idea_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(admin_keyboard(idea_id).inline_keyboard + ((InlineKeyboardButton("📥 К новым", callback_data="admin:inbox"),),))


async def inbox(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not allowed(update, context):
        if update.effective_message and not update.callback_query:
            await update.effective_message.reply_text("Этот раздел для администратора. Секретный клуб, увы. 🕶")
        return
    rows = await storage(context).list_new_ideas()
    text = "<b>Новые заявки</b> 📥\nВыберите заявку:" if rows else "Новых заявок нет. Подозрительно спокойно. ☕"
    await respond(update, text, inbox_keyboard(rows))


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not allowed(update, context):
        if update.effective_message and not update.callback_query:
            await update.effective_message.reply_text("Статистика доступна администратору. 🕶")
        return
    counts = await storage(context).status_counts()
    text = (
        "<b>Сводка</b> 📊\n\n"
        f"🆕 Новые: {counts.get('new', 0)}\n"
        f"🛠 В работе: {counts.get('progress', 0)}\n"
        f"✅ Готово: {counts.get('done', 0)}\n"
        f"🚫 Не берём: {counts.get('declined', 0)}\n\n"
        f"Всего: {sum(counts.values())}"
    )
    await respond(update, text, InlineKeyboardMarkup([[InlineKeyboardButton("📥 Новые заявки", callback_data="admin:inbox")]]))


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not allowed(update, context):
        return
    data = query.data or ""
    if data == "admin:inbox":
        await inbox(update, context)
        return
    if data == "admin:stats":
        await stats(update, context)
        return
    parts = data.split(":")
    if len(parts) == 3 and parts[1] == "view" and parts[2].isdigit():
        idea = await storage(context).get_idea(int(parts[2]))
        if not idea:
            await respond(update, "Заявка не найдена. Может, её унёс офисный полтергейст. 👻")
            return
        await respond(update, idea_card(idea, admin=True), card_keyboard(idea["id"]))
        return
    if len(parts) == 4 and parts[1] == "status" and parts[2].isdigit() and parts[3] in STATUS_LABELS:
        idea, changed = await storage(context).set_status(int(parts[2]), parts[3])
        if not idea:
            await respond(update, "Заявка не найдена.")
            return
        if not changed:
            return
        await respond(update, idea_card(idea, admin=True), card_keyboard(idea["id"]))
        try:
            await context.bot.send_message(
                idea["user_id"],
                f"Заявка <b>#{idea['id']}</b>: {STATUS_LABELS[idea['status']]}.\n{escape(idea['problem'][:120])}",
                parse_mode="HTML",
            )
        except TelegramError:
            logger.exception("Unable to notify author about idea %s", idea["id"])
        return
    await respond(update, "Кнопка устарела. Откройте /inbox.")
