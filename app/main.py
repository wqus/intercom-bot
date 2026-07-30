import asyncio
import logging

from app.bot import bot
from app.database.base import Base
from app.database.engine import engine
from app.dispatcher import dp
from app.models import Request, User  # noqa: F401
from app.services.scheduler import scheduler, setup_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def main() -> None:
    await init_db()
    setup_scheduler(bot)
    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())