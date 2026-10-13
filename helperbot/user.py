"""Employee-facing commands and the four-step submission flow."""

import logging
from html import escape
from random import choice

from telegram import BotCommand, BotCommandScopeChat, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from .storage import Storage
from .ui import PROMPTS, STATUS_LABELS, admin_keyboard, confirm_keyboard, idea_card, menu_keyboard, prompt_keyboard, respond, summary, welcome


logger = logging.getLogger(__name__)
MAX_LENGTH = {"name": 80, "problem": 1200, "optimization": 1200}
NEXT_STEP = {"name": "problem", "problem": "time", "time": "optimization", "optimization": "confirm"}


def storage(context: ContextTypes.DEFAULT_TYPE) -> Storage:
    return context.application.bot_data["storage"]


def is_private(update: Update) -> bool:
    return bool(update.effective_chat and update.effective_chat.type == "private")


async def private_only(update: Update) -> bool:
    if is_private(update):
        return True
    if update.effective_message:
        await update.effective_message.reply_text("Лучше в личку — рабочие боли не обязаны выступать на сцене. 🎭")
    return False


async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, *, greeting: bool = False) -> None:
    if not await private_only(update):
        return
    draft = await storage(context).get_draft(update.effective_user.id)
    text = welcome() if greeting else "Что делаем?"
    await respond(update, text, menu_keyboard(update.effective_user.id == context.application.bot_data["admin_id"], draft["draft_id"] if draft else None))


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if is_private(update) and update.effective_user.id == context.application.bot_data["admin_id"]:
        try:
            await context.bot.set_my_commands(
                [BotCommand("start", "Главное меню"), BotCommand("new", "Рассказать о проблеме"), BotCommand("my", "Мои заявки"), BotCommand("cancel", "Удалить черновик"), BotCommand("help", "Как это работает"), BotCommand("inbox", "Новые заявки"), BotCommand("stats", "Сводка")],
                scope=BotCommandScopeChat(chat_id=update.effective_user.id),
            )
        except TelegramError:
            logger.warning("Unable to register admin command menu")
    await show_menu(update, context, greeting=True)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await private_only(update):
        return
    await respond(update, "Опишите проблему в 4 шага. Время и идею можно пропустить. Перед отправкой всё проверите.\n\n/new — новая заявка\n/my — мои заявки\n/cancel — отменить черновик", menu_keyboard(update.effective_user.id == context.application.bot_data["admin_id"]))


async def new(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await private_only(update):
        return
    user_id = update.effective_user.id
    await storage(context).delete_draft(user_id)
    await storage(context).save_draft(user_id, step="name")
    await show_current(update, context)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await private_only(update):
        return
    await storage(context).delete_draft(update.effective_user.id)
    await respond(update, "Черновик удалён. Бюрократия сегодня проиграла. 🗑", menu_keyboard(update.effective_user.id == context.application.bot_data["admin_id"]))


async def show_current(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    draft = await storage(context).get_draft(update.effective_user.id)
    if not draft:
        await show_menu(update, context)
    elif draft["step"] == "confirm":
        await respond(update, summary(draft), confirm_keyboard(draft["draft_id"]))
    else:
        step = draft["step"].removeprefix("edit_")
        await respond(update, PROMPTS[step], prompt_keyboard(draft))


def parse_hours(text: str) -> int | None:
    value = text.strip().replace(",", ".")
    if not value or len(value) > 6:
        return None
    try:
        hours = float(value)
    except ValueError:
        return None
    if not 0 < hours <= 168 or not hours * 60 >= 1:
        return None
    return round(hours * 60)


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await private_only(update):
        return
    draft = await storage(context).get_draft(update.effective_user.id)
    if not draft:
        await respond(update, "Нажмите «Рассказать о проблеме» — и начнём без совещания. 👇", menu_keyboard(update.effective_user.id == context.application.bot_data["admin_id"]))
        return
    step = draft["step"]
    if step == "confirm":
        await respond(update, "Сначала нажмите «Отправить» или выберите поле для правки. Устное согласование не считается. 🙂", confirm_keyboard(draft["draft_id"]))
        return
    field = step.removeprefix("edit_")
    value = " ".join(update.effective_message.text.split())
    if field == "time":
        minutes = parse_hours(value)
        if minutes is None:
            await respond(update, "Нужно число часов от 0 до 168. Например, <code>2</code> или <code>1,5</code>. Или пропустите.", prompt_keyboard(draft))
            return
        fields = {"weekly_minutes": minutes}
    else:
        if not value:
            await respond(update, "Пусто не приму — я бот, но не настолько формальный. 🙂", prompt_keyboard(draft))
            return
        if len(value) > MAX_LENGTH[field]:
            await respond(update, f"Короткая версия, пожалуйста: максимум {MAX_LENGTH[field]} символов. Сейчас {len(value)}.", prompt_keyboard(draft))
            return
        fields = {field: value}
    next_step = "confirm" if step.startswith("edit_") else NEXT_STEP[field]
    await storage(context).save_draft(update.effective_user.id, step=next_step, **fields)
    await show_current(update, context)


async def my_ideas(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await private_only(update):
        return
    rows = await storage(context).list_user_ideas(update.effective_user.id)
    if not rows:
        await respond(update, "Пока пусто. Похоже, все процессы работают идеально. Подозрительно. 🤨", menu_keyboard(update.effective_user.id == context.application.bot_data["admin_id"]))
        return
    lines = ["<b>Ваши последние заявки</b> 📂"]
    for idea in rows:
        preview = idea["problem"].replace("\n", " ")[:90]
        if len(idea["problem"]) > 90:
            preview += "…"
        lines.append(f"\n<b>#{idea['id']}</b> · {STATUS_LABELS[idea['status']]}\n{escape(preview)}")
    buttons = [[InlineKeyboardButton(f"📄 Открыть #{idea['id']}", callback_data=f"menu:idea:{idea['id']}")] for idea in rows]
    buttons.append([InlineKeyboardButton("🏠 Меню", callback_data="menu:home")])
    await respond(update, "\n".join(lines), InlineKeyboardMarkup(buttons))


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not is_private(update):
        return
    data = query.data or ""
    if data == "menu:new":
        await new(update, context)
    elif data == "menu:mine":
        await my_ideas(update, context)
    elif data == "menu:help":
        await help_command(update, context)
    elif data == "menu:home":
        await show_menu(update, context)
    elif data.startswith("menu:idea:") and data.removeprefix("menu:idea:").isdigit():
        idea = await storage(context).get_idea(int(data.removeprefix("menu:idea:")))
        if not idea or idea["user_id"] != update.effective_user.id:
            await respond(update, "Эта заявка недоступна.")
            return
        await respond(update, idea_card(idea), InlineKeyboardMarkup([[InlineKeyboardButton("📂 К моим заявкам", callback_data="menu:mine")]]))
    elif data.startswith("draft:"):
        parts = data.split(":")
        if len(parts) not in {3, 4}:
            return
        action, draft_id = parts[1:3]
        draft = await storage(context).get_draft(update.effective_user.id)
        if not draft or draft["draft_id"] != draft_id:
            await respond(update, "Эта кнопка от старого черновика. Откройте актуальный через /start.")
            return
        if action == "resume" and len(parts) == 3:
            await show_current(update, context)
        elif action == "cancel" and len(parts) == 3:
            await cancel(update, context)
        elif action == "skip" and len(parts) == 4:
            field = parts[3]
            if field in {"time", "optimization"} and draft["step"] in {field, f"edit_{field}"}:
                next_step = "confirm" if draft["step"].startswith("edit_") else NEXT_STEP[field]
                key = "weekly_minutes" if field == "time" else "optimization"
                await storage(context).save_draft(update.effective_user.id, step=next_step, **{key: None})
                await show_current(update, context)
            else:
                await respond(update, "Этот шаг уже позади. Вернёмся к текущему.")
        elif action == "edit" and len(parts) == 4 and draft["step"] == "confirm" and parts[3] in NEXT_STEP:
            await storage(context).save_draft(update.effective_user.id, step=f"edit_{parts[3]}")
            await show_current(update, context)
        elif action == "submit" and len(parts) == 3 and draft["step"] == "confirm":
            idea = await storage(context).submit_draft(update.effective_user.id, update.effective_user.username)
            if not idea:
                await respond(update, "Не удалось отправить. Откройте /start и попробуйте ещё раз.")
                return
            await respond(update, choice(("Заявка отправлена. Пусть процесс теперь нервничает. 😏", "Готово! Проблема официально перестала быть только вашей. 📬", "Отправлено. Таблица Excel где-то вздрогнула. 📊")), menu_keyboard(update.effective_user.id == context.application.bot_data["admin_id"]))
            try:
                await context.bot.send_message(context.application.bot_data["admin_id"], idea_card(idea, admin=True), parse_mode="HTML", reply_markup=admin_keyboard(idea["id"]))
            except TelegramError:
                logger.exception("Unable to notify admin about idea %s", idea["id"])
        else:
            await respond(update, "Кнопка уже неактуальна. Продолжим с текущего шага.")
    else:
        await respond(update, "Кнопка устарела. Откройте /start.")


async def unsupported(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await private_only(update):
        await update.effective_message.reply_text("Пока понимаю только текст. Да, робот с ограничениями. 🤖")


async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await private_only(update):
        await update.effective_message.reply_text("Такой команды нет. Откройте /help — там короткий список.")
