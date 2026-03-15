import logging
from aiogram import Bot
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database.crud import get_entry, increment_remind_count
from datetime import datetime, timedelta

# ── ЛОГИРОВАНИЕ ───────────────────────────────────────────────────────────
logger = logging.getLogger(__name__)
# ─────────────────────────────────────────────────────────────────────────


async def send_reminder(bot: Bot, entry_id: int, user_id: int):
    """Отправить напоминание пользователю"""
    entry = get_entry(entry_id)

    if not entry:
        logger.warning(f"send_reminder | запись не найдена | entry={entry_id}")
        return

    if entry.is_done or entry.archived_at:
        logger.info(f"send_reminder | пропущено (выполнено/архив) | entry={entry_id}")
        return

    increment_remind_count(entry_id)
    entry = get_entry(entry_id)

    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Сделал", callback_data=f"done_{entry_id}")
    builder.button(text="⏰ Через час", callback_data=f"snooze_1h_{entry_id}")
    builder.button(text="🌅 Завтра", callback_data=f"snooze_tomorrow_{entry_id}")

    if entry.remind_count >= 7:
        builder.button(text="🗄 Архивировать", callback_data=f"archive_{entry_id}")

    builder.adjust(2)

    if entry.source == "guest" and entry.guest_name:
        text = (
            f"📩 Сообщение от {entry.guest_name}:\n\n"
            f"📌 {entry.summary}\n\n"
            f"Напоминаю {entry.remind_count}-й раз"
        )
    else:
        text = (
            f"⏰ Напоминание!\n\n"
            f"📌 {entry.summary}\n\n"
            f"Напоминаю {entry.remind_count}-й раз"
        )

    await bot.send_message(
        user_id,
        text,
        reply_markup=builder.as_markup()
    )

    logger.info(f"send_reminder ОТПРАВЛЕНО | entry={entry_id} | user={user_id} | раз={entry.remind_count}")

    from services.scheduler import schedule_reminder
    next_remind = datetime.utcnow() + timedelta(days=1)
    schedule_reminder(bot, entry_id, user_id, next_remind)
