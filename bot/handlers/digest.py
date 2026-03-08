from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router()


@router.message(Command("digest"))
async def cmd_digest(message: Message):
    """Тестовая команда для ручного вызова сводки"""
    from services.digest_service import generate_digest
    import main as app

    await message.answer("Генерирую сводку... 🌙")
    await generate_digest(app.bot, message.from_user.id, message.from_user.first_name)
