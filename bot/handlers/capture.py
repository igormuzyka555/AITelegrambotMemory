from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import StateFilter
from aiogram.utils.keyboard import InlineKeyboardBuilder
from services.openai_service import transcribe, classify, CATEGORY_EMOJI
from database.crud import save_entry
from datetime import datetime, timedelta
import os
import tempfile

router = Router()


class CaptureFSM(StatesGroup):
    waiting_for_custom_time = State()


async def ask_when_to_remind(message: Message, summary: str, entry_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text="⏱ 30 минут", callback_data=f"remind_30m_{entry_id}")
    builder.button(text="🕐 1 час", callback_data=f"remind_1h_{entry_id}")
    builder.button(text="🕒 2 часа", callback_data=f"remind_2h_{entry_id}")
    builder.button(text="🌙 Вечером", callback_data=f"remind_evening_{entry_id}")
    builder.button(text="🌅 Завтра утром", callback_data=f"remind_tomorrow_{entry_id}")
    builder.button(text="✏️ Своё время", callback_data=f"remind_custom_{entry_id}")
    builder.adjust(2)

    await message.answer(
        f"✅ Задача: {summary}\n\nКогда напомнить?",
        reply_markup=builder.as_markup()
    )


@router.message(F.text & ~F.text.startswith("/"), StateFilter(None))
async def handle_text(message: Message, state: FSMContext):
    t = message.text.lower()
    if t.startswith("передаю сообщение для") or t.startswith("передаю сообщения для") or t.startswith("передай сообщение для"):
        return

    await message.answer("Записываю... 🧠")

    result = await classify(message.text)

    entry_id = save_entry(
        user_id=message.from_user.id,
        source=result.get("source", "owner"),
        raw_text=message.text,
        category=result.get("category"),
        summary=result.get("summary"),
        is_done=False
    )

    emoji = CATEGORY_EMOJI.get(result.get("category"), "📝")
    summary = result.get("summary", message.text[:50])

    if result.get("category") in ("task", "repeat"):
        if result.get("has_explicit_time") and result.get("remind_at"):
            # GPT определил конкретное время — планируем сразу
            from services.scheduler import schedule_reminder
            import main as app
            remind_at = datetime.fromisoformat(result.get("remind_at"))
            schedule_reminder(app.bot, entry_id, message.from_user.id, remind_at)
            await message.answer(f"{emoji} Задача: {summary}\nНапомню в указанное время. ⏰")
        else:
            # Время не указано — спрашиваем пользователя
            await ask_when_to_remind(message, summary, entry_id)
    else:
        await message.answer(f"{emoji} {summary}")


@router.message(F.voice)
async def handle_voice(message: Message, state: FSMContext):
    await message.answer("Записываю... 🧠")

    voice = message.voice
    file = await message.bot.get_file(voice.file_id)

    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        tmp_path = tmp.name

    await message.bot.download_file(file.file_path, tmp_path)

    try:
        text = await transcribe(tmp_path)
        result = await classify(text)

        entry_id = save_entry(
            user_id=message.from_user.id,
            source=result.get("source", "owner"),
            raw_text=text,
            transcription=text,
            category=result.get("category"),
            summary=result.get("summary"),
            is_done=False
        )

        emoji = CATEGORY_EMOJI.get(result.get("category"), "📝")
        summary = result.get("summary", text[:50])

        if result.get("category") in ("task", "repeat"):
            if result.get("has_explicit_time") and result.get("remind_at"):
                # GPT определил конкретное время — планируем сразу
                from services.scheduler import schedule_reminder
                import main as app
                remind_at = datetime.fromisoformat(result.get("remind_at"))
                schedule_reminder(app.bot, entry_id, message.from_user.id, remind_at)
                await message.answer(f"{emoji} Задача: {summary}\nНапомню в указанное время. ⏰")
            else:
                # Время не указано — спрашиваем пользователя
                await ask_when_to_remind(message, summary, entry_id)
        else:
            await message.answer(f"{emoji} {summary}")

    finally:
        os.remove(tmp_path)


@router.callback_query(F.data.startswith("remind_"))
async def handle_reminder_choice(callback: CallbackQuery, state: FSMContext):
    from database.crud import update_entry_remind_at, get_entry
    from services.scheduler import schedule_reminder, cancel_reminder
    import main as app

    parts = callback.data.split("_")
    entry_id = int(parts[-1])
    choice = "_".join(parts[1:-1])

    import pytz
    moscow_tz = pytz.timezone("Europe/Moscow")
    now = datetime.now(moscow_tz)

    if choice == "30m":
        remind_at = now + timedelta(minutes=30)
        label = "через 30 минут"
    elif choice == "1h":
        remind_at = now + timedelta(hours=1)
        label = "через 1 час"
    elif choice == "2h":
        remind_at = now + timedelta(hours=2)
        label = "через 2 часа"
    elif choice == "evening":
        remind_at = now.replace(hour=19, minute=0, second=0, microsecond=0)
        if remind_at < now:
            remind_at += timedelta(days=1)
        label = "сегодня вечером в 19:00"
    elif choice == "tomorrow":
        remind_at = (now + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
        label = "завтра утром в 9:00"
    elif choice == "custom":
        await state.update_data(entry_id=entry_id)
        await state.set_state(CaptureFSM.waiting_for_custom_time)
        await callback.message.answer(
            "Напиши время — например:\n«через 40 минут», «в 15:30», «завтра в 11»"
        )
        await callback.answer()
        return
    else:
        await callback.answer()
        return

    entry = get_entry(entry_id)
    update_entry_remind_at(entry_id, remind_at)
    cancel_reminder(entry_id)
    schedule_reminder(app.bot, entry_id, entry.user_id, remind_at)

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(f"⏰ Напомню {label}!")
    await callback.answer()


@router.message(CaptureFSM.waiting_for_custom_time)
async def handle_custom_time(message: Message, state: FSMContext):
    from database.crud import update_entry_remind_at, get_entry
    from services.openai_service import parse_time
    from services.scheduler import schedule_reminder, cancel_reminder
    import main as app

    data = await state.get_data()
    entry_id = data.get("entry_id")

    remind_at = await parse_time(message.text)

    if remind_at:
        entry = get_entry(entry_id)
        update_entry_remind_at(entry_id, remind_at)
        cancel_reminder(entry_id)
        schedule_reminder(app.bot, entry_id, entry.user_id, remind_at)
        await message.answer(f"⏰ Напомню {remind_at.strftime('%d.%m в %H:%M')}!")
    else:
        await message.answer("Не понял время 😕 Попробуй иначе, например «завтра в 10:00»")
        return

    await state.clear()