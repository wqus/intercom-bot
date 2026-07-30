from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from app.core.dependencies import get_db
from app.keyboards.statistics import statistics_keyboard
from app.repositories.user_repository import UsersRepository

router = Router()


@router.message(CommandStart())
async def start(message: Message):
    if message.from_user:
        async for session in get_db():
            repo = UsersRepository(session)
            await repo.upsert_user(
                telegram_id=message.from_user.id,
                username=message.from_user.username,
                full_name=message.from_user.full_name,
            )
            break

    await message.answer(
        "Добро пожаловать.",
        reply_markup=statistics_keyboard,
    )