import asyncio
import logging

from app.bot import bot
from app.dispatcher import dp
from app.services.scheduler import scheduler, setup_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


async def main() -> None:
    # IMPORTANT: this bot does NOT run create_all() against the main DB.
    # The Intercom application owns the schema. This service only reads the
    # existing tables and writes Telegram-bot users.
    setup_scheduler(bot)
    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
