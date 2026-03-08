from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, LabeledPrice, PreCheckoutQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database.crud import get_or_create_user, update_user
import os

router = Router()


class OnboardingFSM(StatesGroup):
    waiting_for_digest_time = State()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    from services.scheduler import schedule_trial_ending
    import main as app

    user = get_or_create_user(
        user_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name
    )

    # Если уже проходил онбординг
    if user.is_onboarded:
        if user.role == "guest":
            # Гость возвращается — даём выбор
            builder = InlineKeyboardBuilder()
            builder.button(text="📩 Отправить сообщение партнёру", callback_data="guest_send_new")
            builder.button(text="🧠 Переключиться в режим пользователя", callback_data="switch_to_owner")
            builder.adjust(1)
            await message.answer(
                f"С возвращением, {user.first_name}! 🤝\n\n"
                f"Что хочешь сделать?",
                reply_markup=builder.as_markup()
            )
        else:
            # Хозяин возвращается — даём выбор
            builder = InlineKeyboardBuilder()
            builder.button(text="⏰ Изменить время сводки", callback_data="change_digest_time")
            builder.button(text="🤝 Переключиться в режим партнёра", callback_data="switch_to_guest")
            builder.adjust(1)
            await message.answer(
                f"С возвращением, {user.first_name}! 🧠\n\n"
                f"Просто говори или пиши — я запомню всё. 🎙️\n"
                f"Сводка приходит в {user.digest_time}",
                reply_markup=builder.as_markup()
            )
        return

    # Новый пользователь — выбор роли
    builder = InlineKeyboardBuilder()
    builder.button(text="🧠  Хочу записывать свои задачи и идеи", callback_data="role_owner")
    builder.button(text="🤝  Хочу отправить задачу другому человеку", callback_data="role_guest")
    builder.adjust(1)

    await message.answer(
        f"Привет, {message.from_user.first_name}! 👋\n\n"
        f"Я твой Второй Мозг — запомню всё что ты скажешь или напишешь.\n\n"
        f"Идеи, задачи, мысли на ходу — просто говори голосом или пиши текстом. "
        f"Я разберу, сохраню и напомню когда нужно.\n\n"
        f"Сначала скажи кем ты хочешь быть пользователем или партнером/гостем \n\n"
        f"У тебя есть 7 дней бесплатно. Начнём?",
        reply_markup=builder.as_markup()
    )


# ── ВЫБОР РОЛИ ────────────────────────────────────────────────────────────
@router.callback_query(F.data == "role_owner")
async def role_owner(callback: CallbackQuery, state: FSMContext):
    from services.scheduler import schedule_trial_ending
    import main as app

    user = get_or_create_user(callback.from_user.id)
    update_user(callback.from_user.id, role="owner")

    schedule_trial_ending(
        bot=app.bot,
        user_id=user.user_id,
        first_name=user.first_name,
        trial_start=user.trial_start
    )

    await callback.message.answer(
        f"Отлично! 🧠\n\n"
        f"Тогда начнем.\n\n"
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="🌙 21:00", callback_data="digest_21:00")
    builder.button(text="🌆 20:00", callback_data="digest_20:00")
    builder.button(text="🌃 22:00", callback_data="digest_22:00")
    builder.button(text="✏️ Другое время", callback_data="digest_custom")
    builder.adjust(2)

    await callback.message.answer(
        "В какое время присылать вечернюю сводку дня?",
        reply_markup=builder.as_markup()
    )
    await state.set_state(OnboardingFSM.waiting_for_digest_time)
    await callback.answer()


@router.callback_query(F.data == "role_guest")
async def role_guest(callback: CallbackQuery, state: FSMContext):
    update_user(callback.from_user.id, role="guest", is_onboarded=True)

    await callback.message.answer(
        f"Отлично, {callback.from_user.first_name}! 🤝\n\n"
        f"Ты можешь отправлять сообщения-задачи пользователям бота.\n"
        f"Когда они выполнят задачу — ты получишь уведомление!\n\n"
        f"Напиши /guest чтобы отправить сообщение."
    )
    await callback.answer()


# ── ГОСТЬ ВОЗВРАЩАЕТСЯ — НОВОЕ СООБЩЕНИЕ ─────────────────────────────────
@router.callback_query(F.data == "guest_send_new")
async def guest_send_new(callback: CallbackQuery, state: FSMContext):
    from bot.handlers.guest import GuestFSM
    await state.set_state(GuestFSM.waiting_for_owner)
    await callback.message.answer(
        "Напиши username того кому хочешь передать сообщение\n"
        "(например: @muzyka410):"
    )
    await callback.answer()


# ── ПЕРЕКЛЮЧЕНИЕ РОЛЕЙ ───────────────────────────────────────────────────
@router.callback_query(F.data == "switch_to_owner")
async def switch_to_owner(callback: CallbackQuery, state: FSMContext):
    from services.scheduler import schedule_trial_ending
    import main as app
    user = get_or_create_user(callback.from_user.id)
    update_user(callback.from_user.id, role="owner")

    builder = InlineKeyboardBuilder()
    builder.button(text="🌙 21:00", callback_data="digest_21:00")
    builder.button(text="🌆 20:00", callback_data="digest_20:00")
    builder.button(text="🌃 22:00", callback_data="digest_22:00")
    builder.button(text="✏️ Другое время", callback_data="digest_custom")
    builder.adjust(2)

    await callback.message.answer(
        "🧠 Переключился в режим пользователя!\n\n"
        "Теперь просто говори или пиши — я запомню всё.\n\n"
        "В какое время присылать вечернюю сводку?",
        reply_markup=builder.as_markup()
    )
    await state.set_state(OnboardingFSM.waiting_for_digest_time)
    await callback.answer()


@router.callback_query(F.data == "switch_to_guest")
async def switch_to_guest(callback: CallbackQuery, state: FSMContext):
    update_user(callback.from_user.id, role="guest")
    await callback.message.answer(
        "🤝 Переключился в режим партнёра!\n\n"
        "Напиши /guest чтобы отправить сообщение партнёру."
    )
    await callback.answer()


# ── ВЫБОР ВРЕМЕНИ СВОДКИ ──────────────────────────────────────────────────
@router.callback_query(F.data.startswith("digest_"))
async def got_digest_time(callback: CallbackQuery, state: FSMContext):
    time_value = callback.data.replace("digest_", "")

    if time_value == "custom":
        await callback.message.answer("Напиши время в формате ЧЧ:ММ, например 19:30:")
        return

    update_user(callback.from_user.id, digest_time=time_value, is_onboarded=True)
    await state.clear()

    await callback.message.answer(
        f"Готово! Сводка будет приходить в {time_value} ✅\n\n"
        f"Теперь просто говори или пиши — я запомню всё. 🎙️"
    )
    await callback.answer()


@router.message(OnboardingFSM.waiting_for_digest_time)
async def got_custom_time(message: Message, state: FSMContext):
    time_value = message.text.strip()
    update_user(message.from_user.id, digest_time=time_value, is_onboarded=True)
    await state.clear()

    await message.answer(
        f"Готово! Сводка будет приходить в {time_value} ✅\n\n"
        f"Теперь просто говори или пиши — я запомню всё. 🎙️"
    )


# ── ПОДПИСКА ──────────────────────────────────────────────────────────────
@router.callback_query(F.data == "subscribe")
async def cmd_subscribe(callback: CallbackQuery):
    await callback.message.answer_invoice(
        title="Второй Мозг — подписка",
        description="Доступ на 30 дней. Все функции без ограничений.",
        payload="subscription_30days",
        currency="RUB",
        prices=[LabeledPrice(label="Подписка 30 дней", amount=29900)],
        provider_token=os.getenv("PAYMENT_TOKEN"),
    )
    await callback.answer()


@router.pre_checkout_query()
async def pre_checkout(pre_checkout_query: PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment(message: Message):
    from datetime import datetime, timedelta
    update_user(
        message.from_user.id,
        is_subscribed=True,
        subscription_end=datetime.utcnow() + timedelta(days=30)
    )
    await message.answer(
        "Подписка оформлена! 🎉\n\n"
        "Следующие 30 дней Второй Мозг твой. "
        "Просто говори или пиши — я помню всё. 🧠"
    )


@router.callback_query(F.data == "change_digest_time")
async def change_digest_time(callback: CallbackQuery, state: FSMContext):
    builder = InlineKeyboardBuilder()
    builder.button(text="🌙 21:00", callback_data="digest_21:00")
    builder.button(text="🌆 20:00", callback_data="digest_20:00")
    builder.button(text="🌃 22:00", callback_data="digest_22:00")
    builder.button(text="✏️ Другое время", callback_data="digest_custom")
    builder.adjust(2)

    await callback.message.answer(
        "Выбери новое время сводки:",
        reply_markup=builder.as_markup()
    )
    await state.set_state(OnboardingFSM.waiting_for_digest_time)
    await callback.answer()
