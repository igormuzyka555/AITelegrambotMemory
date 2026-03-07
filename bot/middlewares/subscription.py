from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from database.crud import get_or_create_user
from datetime import datetime
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import Callable, Awaitable, Any


class SubscriptionMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, dict], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: dict
    ) -> Any:
        # Получаем user_id
        if isinstance(event, Message):
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id
        else:
            return await handler(event, data)

        # ВРЕМЕННО ОТКЛЮЧЕНО — для тестирования
        return await handler(event, data)

        # user = get_or_create_user(user_id)
        # if user.is_subscribed:
        #     return await handler(event, data)
        # if user.trial_start:
        #     days_passed = (datetime.utcnow() - user.trial_start).days
        #     if days_passed <= 7:
        #         return await handler(event, data)
        # builder = InlineKeyboardBuilder()
        # builder.button(text="💜 Оформить подписку — 299 ₽/мес", callback_data="subscribe")
        # text = (
        #     "Твой бесплатный период закончился 🙁\n\n"
        #     "Все твои записи сохранены. Чтобы продолжить — "
        #     "оформи подписку за 299 ₽ в месяц."
        # )
        # if isinstance(event, Message):
        #     await event.answer(text, reply_markup=builder.as_markup())
        # elif isinstance(event, CallbackQuery):
        #     await event.message.answer(text, reply_markup=builder.as_markup())
        # return
