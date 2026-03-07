from aiogram import Router, F
from aiogram.types import CallbackQuery
from database.crud import mark_done, archive_entry, get_entry
from services.scheduler import schedule_reminder, cancel_reminder
from datetime import datetime, timedelta

router = Router()


# ── СДЕЛАЛ ✓ ──────────────────────────────────────────
@router.callback_query(F.data.startswith("done_"))
async def handle_done(callback: CallbackQuery):
    entry_id = int(callback.data.split("_")[1])

    # Отменяем все будущие напоминания
    cancel_reminder(entry_id)

    # Отмечаем как выполненное
    mark_done(entry_id)

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("✅ Зафиксировал! Молодец 💪")
    await callback.answer()


# ── ПОЗЖЕ — ЧЕРЕЗ ЧАС ─────────────────────────────────
@router.callback_query(F.data.startswith("snooze_1h_"))
async def handle_snooze_1h(callback: CallbackQuery):
    import main as app
    entry_id = int(callback.data.split("_")[2])
    entry = get_entry(entry_id)

    if not entry:
        await callback.answer()
        return

    remind_at = datetime.utcnow() + timedelta(hours=1)
    schedule_reminder(app.bot, entry_id, entry.user_id, remind_at)

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("⏰ Напомню через час!")
    await callback.answer()


# ── ПОЗЖЕ — ЗАВТРА ────────────────────────────────────
@router.callback_query(F.data.startswith("snooze_tomorrow_"))
async def handle_snooze_tomorrow(callback: CallbackQuery):
    import main as app
    entry_id = int(callback.data.split("_")[2])
    entry = get_entry(entry_id)

    if not entry:
        await callback.answer()
        return

    # Завтра в то же время
    now = datetime.utcnow()
    remind_at = now + timedelta(days=1)
    schedule_reminder(app.bot, entry_id, entry.user_id, remind_at)

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("🌅 Напомню завтра в это же время!")
    await callback.answer()


# ── АРХИВИРОВАТЬ ──────────────────────────────────────
@router.callback_query(F.data.startswith("archive_"))
async def handle_archive(callback: CallbackQuery):
    entry_id = int(callback.data.split("_")[1])

    # Отменяем все будущие напоминания
    cancel_reminder(entry_id)

    # Архивируем — НЕ ставим is_done=true
    archive_entry(entry_id)

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("🗄 Задача архивирована.")
    await callback.answer()