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

    # Если уже проходил онбординг — приветствуем
    if user.is_onboarded:
        builder = InlineKeyboardBuilder()
        builder.button(text="⏰ Изменить время сводки", callback_data="change_digest_time")

        await message.answer(
            f"С возвращением, {user.first_name}! 🧠\n\n"
            f"Просто говори или пиши — я запомню всё. 🎙️\n"
            f"Сводка приходит в {user.digest_time}",
            reply_markup=builder.as_markup()
        )
        return

    # Планируем напоминание об окончании триала
    schedule_trial_ending(
        bot=app.bot,
        user_id=user.user_id,
        first_name=user.first_name,
        trial_start=user.trial_start
    )

    await message.answer(
        f"Привет, {message.from_user.first_name}! 🧠\n\n"
        f"Я твой Второй Мозг — запомню всё что ты скажешь или напишешь.\n\n"
        f"Идеи, задачи, мысли на ходу — просто говори голосом или пиши текстом. "
        f"Я разберу, сохраню и напомню когда нужно.\n\n"
        f"У тебя есть 7 дней бесплатно. Начнём?"
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="🌙 21:00", callback_data="digest_21:00")
    builder.button(text="🌆 20:00", callback_data="digest_20:00")
    builder.button(text="🌃 22:00", callback_data="digest_22:00")
    builder.button(text="✏️ Другое время", callback_data="digest_custom")
    builder.adjust(2)

    await message.answer(
        "В какое время присылать вечернюю сводку дня?",
        reply_markup=builder.as_markup()
    )
    await state.set_state(OnboardingFSM.waiting_for_digest_time)


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


# ── ПОДПИСКА ──────────────────────────────────────────
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