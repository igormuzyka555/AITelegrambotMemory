import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv
from database.crud import init_db
from services.scheduler import start_scheduler, schedule_daily_digests
from bot.middlewares.subscription import SubscriptionMiddleware
import os

load_dotenv()

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
            # Конвертируем remind_at в московское время
            remind_at = entry.remind_at
            if remind_at.tzinfo is None:
                remind_at = pytz.utc.localize(remind_at).astimezone(moscow_tz)

            # Если время уже прошло — напомним через 1 минуту
            if remind_at < now:
                from datetime import timedelta
                remind_at = now + timedelta(minutes=1)

            schedule_reminder(bot, entry.id, entry.user_id, remind_at)
            restored += 1

    print(f"Восстановлено напоминаний: {restored}")


async def main():
    init_db()
    print("База данных готова!")

    # Подключаем middleware
    dp.message.middleware(SubscriptionMiddleware())
    dp.callback_query.middleware(SubscriptionMiddleware())

    # Подключаем роутеры
    from bot.handlers import onboarding, guest, capture, recall, digest, views
    dp.include_router(onboarding.router)
    dp.include_router(guest.router)
    dp.include_router(capture.router)
    dp.include_router(recall.router)
    dp.include_router(digest.router)
    dp.include_router(views.router)

    # Запускаем планировщик
    start_scheduler()
    print("Планировщик запущен!")

    # Восстанавливаем напоминания из БД
    restore_reminders()

    # Планируем вечерние сводки для всех пользователей
    schedule_daily_digests(bot)

    # Устанавливаем меню команд
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
    print("Меню команд установлено!")

    print("Бот запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
