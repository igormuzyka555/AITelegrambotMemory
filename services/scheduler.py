import pytz
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from datetime import datetime, timedelta
from aiogram import Bot
from aiogram.utils.keyboard import InlineKeyboardBuilder

# ── ЛОГИРОВАНИЕ ───────────────────────────────────────────────────────────
logger = logging.getLogger(__name__)
# ─────────────────────────────────────────────────────────────────────────

MOSCOW_TZ = pytz.timezone("Europe/Moscow")
scheduler = AsyncIOScheduler(timezone=MOSCOW_TZ)


def start_scheduler():
    scheduler.start()
    logger.info("Планировщик APScheduler запущен")


# ── ТРИАЛ ─────────────────────────────────────────────
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
    logger.info(f"Отправлено уведомление об окончании триала | user={user_id}")


def schedule_trial_ending(bot: Bot, user_id: int, first_name: str, trial_start: datetime):
    remind_at = trial_start + timedelta(days=5)

    if remind_at <= datetime.utcnow():
        return

    scheduler.add_job(
        send_trial_ending,
        trigger=DateTrigger(run_date=remind_at),
        args=[bot, user_id, first_name],
        id=f"trial_{user_id}",
        replace_existing=True
    )
    logger.info(f"Триал запланирован | user={user_id} | время={remind_at}")


# ── НАПОМИНАНИЯ О ЗАДАЧАХ ──────────────────────────────
def schedule_reminder(bot: Bot, entry_id: int, user_id: int, remind_at: datetime):
    """Запланировать напоминание о задаче"""
    if remind_at.tzinfo is None:
        remind_at = pytz.utc.localize(remind_at).astimezone(MOSCOW_TZ)

    scheduler.add_job(
        send_reminder_job,
        trigger=DateTrigger(run_date=remind_at),
        args=[bot, entry_id, user_id],
        id=f"reminder_{entry_id}",
        replace_existing=True
    )
    logger.info(f"REMINDER запланирован | entry={entry_id} | user={user_id} | время={remind_at}")


async def send_reminder_job(bot: Bot, entry_id: int, user_id: int):
    """Джоб который запускает APScheduler"""
    logger.info(f"REMINDER сработал | entry={entry_id} | user={user_id}")
    from services.reminder_service import send_reminder
    await send_reminder(bot, entry_id, user_id)


def cancel_reminder(entry_id: int):
    """Отменить все будущие напоминания для задачи"""
    job_id = f"reminder_{entry_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
        logger.info(f"REMINDER отменён | entry={entry_id}")


# ── ВЕЧЕРНИЕ СВОДКИ ────────────────────────────────────────────────────

def schedule_daily_digests(bot: Bot):
    """Планируем ежедневные сводки для всех активных пользователей"""
    from database.crud import get_all_owner_users
    from apscheduler.triggers.cron import CronTrigger

    users = get_all_owner_users()
    count = 0
    for user in users:
        if not user.digest_time:
            continue
        try:
            hour, minute = user.digest_time.split(":")
            scheduler.add_job(
                send_digest_job,
                trigger=CronTrigger(hour=int(hour), minute=int(minute), timezone=MOSCOW_TZ),
                args=[bot, user.user_id, user.first_name],
                id=f"digest_{user.user_id}",
                replace_existing=True
            )
            count += 1
        except Exception as e:
            logger.error(f"Ошибка планирования сводки | user={user.user_id} | {e}")

    logger.info(f"Сводки запланированы для {count} пользователей")


async def send_digest_job(bot: Bot, user_id: int, first_name: str):
    """Джоб отправки сводки"""
    logger.info(f"Сводка отправляется | user={user_id}")
    from services.digest_service import generate_digest
    await generate_digest(bot, user_id, first_name)
