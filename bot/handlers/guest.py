from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters import Command
from database.crud import save_entry, get_user_by_username
from datetime import datetime, timedelta

router = Router()


class GuestFSM(StatesGroup):
    waiting_for_owner = State()       # Шаг 1: для кого сообщение
    waiting_for_name = State()        # Шаг 2: имя гостя
    waiting_for_message = State()     # Шаг 3: сообщение
    waiting_for_comment = State()     # Шаг 4: комментарий
    waiting_for_custom_time = State() # Шаг 5: своё время


# ── /guest — вход в гостевой режим ───────────────────────────────────────
@router.message(Command("guest"))
async def guest_start(message: Message, state: FSMContext):
    await state.set_state(GuestFSM.waiting_for_owner)
    await message.answer(
        "👋 Привет! Ты оставляешь сообщение для пользователя бота.\n\n"
        "Напиши username того кому хочешь передать сообщение\n"
        "(например: @muzyka410):"
    )


# ── ШАГ 1: ищем хозяина по username ──────────────────────────────────────
@router.message(GuestFSM.waiting_for_owner)
async def guest_got_owner(message: Message, state: FSMContext):
    username = message.text.strip().lstrip("@").lower()
    owner = get_user_by_username(username)

    if not owner:
        await message.answer(
            f"❌ Пользователь @{username} не найден.\n\n"
            f"Проверь username и попробуй снова:"
        )
        return

    await state.update_data(owner_id=owner.user_id, owner_name=owner.first_name)
    await state.set_state(GuestFSM.waiting_for_name)

    await message.answer(
        f"✅ Нашёл! Пишешь для {owner.first_name}.\n\n"
        f"Как тебя зовут?"
    )


# ── ШАГ 2: имя гостя ──────────────────────────────────────────────────────
@router.message(GuestFSM.waiting_for_name)
async def guest_got_name(message: Message, state: FSMContext):
    guest_name = message.text.strip()
    await state.update_data(guest_name=guest_name)
    await state.set_state(GuestFSM.waiting_for_message)

    await message.answer(
        f"Отлично, {guest_name}! 😊\n\n"
        f"Что хочешь передать? Напиши сообщение:"
    )


# ── ШАГ 3: сообщение ──────────────────────────────────────────────────────
@router.message(GuestFSM.waiting_for_message)
async def guest_got_message(message: Message, state: FSMContext):
    await state.update_data(guest_message=message.text.strip())
    await state.set_state(GuestFSM.waiting_for_comment)

    builder = InlineKeyboardBuilder()
    builder.button(text="➡️ Без комментария", callback_data="guest_no_comment")
    builder.adjust(1)

    await message.answer(
        "Хочешь добавить комментарий?\n"
        "Например: «срочно», «до вечера», «не забудь»\n\n"
        "Или нажми кнопку чтобы пропустить:",
        reply_markup=builder.as_markup()
    )


# ── ШАГ 4а: комментарий текстом ───────────────────────────────────────────
@router.message(GuestFSM.waiting_for_comment)
async def guest_got_comment(message: Message, state: FSMContext):
    await state.update_data(guest_comment=message.text.strip())
    await ask_remind_time(message, state)


# ── ШАГ 4б: без комментария ───────────────────────────────────────────────
@router.callback_query(F.data == "guest_no_comment")
async def guest_no_comment(callback: CallbackQuery, state: FSMContext):
    await state.update_data(guest_comment=None)
    await callback.message.edit_reply_markup(reply_markup=None)
    await ask_remind_time(callback.message, state)
    await callback.answer()


# ── ШАГ 5: выбор времени напоминания ─────────────────────────────────────
async def ask_remind_time(message: Message, state: FSMContext):
    builder = InlineKeyboardBuilder()
    builder.button(text="⏱ 30 минут", callback_data="guest_remind_30m")
    builder.button(text="🕐 1 час", callback_data="guest_remind_1h")
    builder.button(text="🕒 2 часа", callback_data="guest_remind_2h")
    builder.button(text="🌙 Вечером", callback_data="guest_remind_evening")
    builder.button(text="🌅 Завтра утром", callback_data="guest_remind_tomorrow")
    builder.button(text="✏️ Своё время", callback_data="guest_remind_custom")
    builder.adjust(2)

    await message.answer(
        "Когда напомнить хозяину?",
        reply_markup=builder.as_markup()
    )


# ── ШАГ 6: обработка выбора времени ──────────────────────────────────────
@router.callback_query(F.data.startswith("guest_remind_"))
async def guest_remind_choice(callback: CallbackQuery, state: FSMContext):
    import pytz
    moscow_tz = pytz.timezone("Europe/Moscow")
    now = datetime.now(moscow_tz)
    choice = callback.data.replace("guest_remind_", "")

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
        await state.set_state(GuestFSM.waiting_for_custom_time)
        await callback.message.answer(
            "Напиши время — например:\n«через 40 минут», «в 15:30», «завтра в 11»"
        )
        await callback.answer()
        return
    else:
        await callback.answer()
        return

    await callback.message.edit_reply_markup(reply_markup=None)
    await state.update_data(remind_at=remind_at.isoformat())
    await finish_guest(callback.message, state, label)
    await callback.answer()


# ── Своё время ────────────────────────────────────────────────────────────
@router.message(GuestFSM.waiting_for_custom_time)
async def guest_custom_time(message: Message, state: FSMContext):
    from services.openai_service import parse_time
    remind_at = await parse_time(message.text)

    if remind_at:
        label = remind_at.strftime("%d.%m в %H:%M")
        await state.update_data(remind_at=remind_at.isoformat())
        await finish_guest(message, state, label)
    else:
        await message.answer("Не понял время 😕 Попробуй иначе, например «завтра в 10:00»")


# ── Финал: сохраняем и уведомляем ────────────────────────────────────────
async def finish_guest(message: Message, state: FSMContext, label: str):
    data = await state.get_data()
    owner_id = data.get("owner_id")
    owner_name = data.get("owner_name")
    guest_name = data.get("guest_name", "Гость")
    guest_message = data.get("guest_message", "")
    guest_comment = data.get("guest_comment")
    remind_at_str = data.get("remind_at")

    remind_at = datetime.fromisoformat(remind_at_str) if remind_at_str else datetime.utcnow() + timedelta(hours=2, minutes=30)

    # Формируем summary с комментарием
    summary = guest_message
    if guest_comment:
        summary = f"{guest_message} (комментарий: {guest_comment})"

    # Сохраняем в БД для хозяина (+ telegram_id гостя для обратного уведомления)
    entry_id = save_entry(
        user_id=owner_id,
        source="guest",
        guest_name=guest_name,
        guest_telegram_id=message.from_user.id,
        raw_text=guest_message,
        category="task",
        summary=summary,
        remind_at=remind_at,
        is_done=False
    )

    # Планируем напоминание хозяину
    from services.scheduler import schedule_reminder
    import main as app
    schedule_reminder(app.bot, entry_id, owner_id, remind_at)

    # Благодарим гостя
    await message.answer(
        f"✅ Готово! {owner_name} получит напоминание {label}.\n\n"
        f"Спасибо, {guest_name}! 🙏"
    )

    await state.clear()
