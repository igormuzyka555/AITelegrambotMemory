import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv
from database.crud import init_db
from services.scheduler import start_scheduler, schedule_daily_digests
from bot.middlewares.subscription import SubscriptionMiddleware
import os

load_dotenv()

# ── ЛОГИРОВАНИЕ ───────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
# ─────────────────────────────────────────────────────────────────────────

bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher(storage=MemoryStorage())


def restore_reminders():
    """Восстанавливаем все незакрытые напоминания из БД после перезапуска"""
    from database.crud import get_all_pending_reminders
    from services.scheduler import schedule_reminder
    from datetime import datetime
    import pytz

    moscow_tz = pytz.timezone("Europe/Moscow")
    now = datetime.now(moscow_tz)
    restored = 0

    entries = get_all_pending_reminders()
    for entry in entries:
        if entry.remind_at:
            remind_at = entry.remind_at
            if remind_at.tzinfo is None:
                remind_at = pytz.utc.localize(remind_at).astimezone(moscow_tz)

            if remind_at < now:
                from datetime import timedelta
                remind_at = now + timedelta(minutes=1)

            schedule_reminder(bot, entry.id, entry.user_id, remind_at)
            restored += 1

    logger.info(f"Восстановлено напоминаний: {restored}")


async def main():
    init_db()
    logger.info("База данных готова!")

    dp.message.middleware(SubscriptionMiddleware())
    dp.callback_query.middleware(SubscriptionMiddleware())

    from bot.handlers import onboarding, guest, capture, recall, digest, views
    dp.include_router(onboarding.router)
    dp.include_router(guest.router)
    dp.include_router(capture.router)
    dp.include_router(recall.router)
    dp.include_router(digest.router)
    dp.include_router(views.router)

    start_scheduler()
    logger.info("Планировщик запущен!")

    restore_reminders()
    schedule_daily_digests(bot)

    from aiogram.types import BotCommand
    await bot.set_my_commands([
        BotCommand(command="start",   description="🏠 Главное меню"),
        BotCommand(command="tasks",   description="📌 Незакрытые задачи"),
        BotCommand(command="today",   description="📅 Все записи за сегодня"),
        BotCommand(command="week",    description="📊 Итоги за неделю"),
        BotCommand(command="ideas",   description="💡 Идеи за 7 дней"),
        BotCommand(command="notes",   description="📝 Заметки за 7 дней"),
        BotCommand(command="memory",  description="🧠 Всё что я знаю о тебе"),
        BotCommand(command="digest",  description="🌙 Сводка за сегодня"),
        BotCommand(command="guest",   description="🤝 Отправить сообщение партнёру"),
    ])
    logger.info("Меню команд установлено!")

    logger.info("Бот запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
