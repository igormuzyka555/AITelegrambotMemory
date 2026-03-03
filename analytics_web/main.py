import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv
from database.crud import init_db
from services.scheduler import start_scheduler, schedule_trial_ending
from bot.middlewares.subscription import SubscriptionMiddleware
import os

load_dotenv()

bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher(storage=MemoryStorage())


async def main():
    init_db()
    print("База данных готова!")

    # Подключаем middleware
    dp.message.middleware(SubscriptionMiddleware())
    dp.callback_query.middleware(SubscriptionMiddleware())

    # Подключаем роутеры
    from bot.handlers import onboarding, capture
    dp.include_router(onboarding.router)
    dp.include_router(capture.router)

    # Запускаем планировщик
    start_scheduler()
    print("Планировщик запущен!")

    print("Бот запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())