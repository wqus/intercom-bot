import asyncio
import logging
from datetime import datetime, timedelta, timezone

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.dependencies import get_db
from app.repositories.statistics_repository import StatisticsRepository
from app.repositories.user_repository import UsersRepository
from app.services.sheets_service import append_daily_stats
from app.services.statistics_service import StatisticsService
from app.utils.formatter import format_statistics

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone=timezone.utc)


async def send_daily_report(bot: Bot) -> None:
    now = datetime.now(timezone.utc)
    end = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start = end - timedelta(days=1)
    report_date = start.date()

    try:
        async for session in get_db():
            stats_repo = StatisticsRepository(session)
            users_repo = UsersRepository(session)

            service = StatisticsService(stats_repo)
            stats = await service.get_statistics(start, end)
            text = "📬 <b>Ежедневный отчёт</b>\n\n" + format_statistics(
                stats, start, end
            )
            user_ids = await users_repo.get_all_telegram_ids()
            break
        else:
            return

        # Google Sheets
        try:
            await asyncio.to_thread(append_daily_stats, stats, report_date)
        except Exception:
            logger.exception("Google Sheets append failed")

        if not user_ids:
            logger.warning("No users in DB, daily report skipped")
            return

        sent = 0
        for user_id in user_ids:
            try:
                await bot.send_message(chat_id=user_id, text=text)
                sent += 1
            except Exception:
                logger.exception("Failed to send daily report to %s", user_id)
            await asyncio.sleep(0.05)

        logger.info("Daily report sent to %s/%s users", sent, len(user_ids))
    except Exception:
        logger.exception("Failed to build/send daily statistics report")


def setup_scheduler(bot: Bot) -> None:
    scheduler.add_job(
        send_daily_report,
        trigger="cron",
        hour=15,
        minute=45,
        kwargs={"bot": bot},
        id="daily_stats",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started")