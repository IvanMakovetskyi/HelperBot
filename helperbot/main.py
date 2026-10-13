"""Polling entry point for the Telegram bot."""

import logging

from telegram import BotCommand, BotCommandScopeChat, Update
from telegram.error import TelegramError
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from .config import Settings
from .storage import Storage
from .user import cancel, help_command, my_ideas, new, on_callback, on_text, start, unsupported


logger = logging.getLogger(__name__)


async def post_init(application: Application) -> None:
    await application.bot_data["storage"].initialize()
    commands = [
        BotCommand("start", "Главное меню"),
        BotCommand("new", "Рассказать о проблеме"),
        BotCommand("my", "Мои заявки"),
        BotCommand("cancel", "Удалить черновик"),
        BotCommand("help", "Как это работает"),
    ]
    try:
        await application.bot.set_my_commands(commands)
        await application.bot.set_my_commands(
            commands + [BotCommand("inbox", "Новые заявки"), BotCommand("stats", "Сводка")],
            scope=BotCommandScopeChat(chat_id=application.bot_data["admin_id"]),
        )
    except TelegramError:
        logger.exception("Unable to register bot commands")


async def post_shutdown(application: Application) -> None:
    await application.bot_data["storage"].close()


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Unhandled update error", exc_info=context.error)
    if isinstance(update, Update) and update.effective_chat and update.effective_chat.type == "private":
        try:
            if update.callback_query:
                await update.callback_query.answer()
            await context.bot.send_message(update.effective_chat.id, "Что-то пошло не так. Попробуйте ещё раз через /start. 🤖")
        except TelegramError:
            logger.warning("Unable to deliver error message")


def build_application(settings: Settings) -> Application:
    application = (
        Application.builder()
        .token(settings.token)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    application.bot_data["storage"] = Storage(settings.database_url)
    application.bot_data["admin_id"] = settings.admin_id
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("new", new))
    application.add_handler(CommandHandler("my", my_ideas))
    application.add_handler(CommandHandler("cancel", cancel))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(on_callback, pattern=r"^(menu:|draft:)"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    application.add_handler(MessageHandler(~filters.TEXT & ~filters.COMMAND, unsupported))
    application.add_error_handler(on_error)
    return application


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    settings = Settings.from_env()
    application = build_application(settings)
    application.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
