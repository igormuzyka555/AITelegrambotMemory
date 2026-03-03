from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from datetime import datetime, timedelta
from aiogram import Bot
from aiogram.utils.keyboard import InlineKeyboardBuilder
import os

scheduler = AsyncIOScheduler()


def start_scheduler():
    scheduler.start()


async def send_trial_ending(bot: Bot, user_id: int, first_name: str):
    builder = InlineKeyboardBuilder()
    builder.button(text="💜 Оформить подписку — 299 ₽/мес", callback_data="subscribe")

    await bot.send_message(
        user_id,
        f"{first_name}, твой бесплатный период заканчивается через 2 дня 🙁\n\n"
        f"Все записи сохранены. Чтобы продолжить пользоваться — "
        f"оформи подписку за 299 ₽ в месяц.",
        reply_markup=builder.as_markup()
    )


def schedule_trial_ending(bot: Bot, user_id: int, first_name: str, trial_start: datetime):
    remind_at = trial_start + timedelta(days=5)

    # Если время уже прошло — не планируем
    if remind_at <= datetime.utcnow():
        return

    scheduler.add_job(
        send_trial_ending,
        trigger=DateTrigger(run_date=remind_at),
        args=[bot, user_id, first_name],
        id=f"trial_{user_id}",
        replace_existing=True
    )