import asyncio
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.config import settings
from app.core.dependencies import get_db
from app.repositories.statistics_repository import StatisticsRepository
from app.repositories.user_repository import UsersRepository
from app.services.sheets_service import append_daily_stats
from app.services.statistics_service import StatisticsService
from app.utils.formatter import format_statistics

logger = logging.getLogger(__name__)

REPORT_TZ = ZoneInfo(settings.REPORT_TIMEZONE)
scheduler = AsyncIOScheduler(timezone=REPORT_TZ)


async def send_daily_report(bot: Bot) -> None:
    now = datetime.now(REPORT_TZ)
    end_local = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start_local = end_local - timedelta(days=1)

    # PostgreSQL timestamptz comparisons are safest with aware datetimes.
    start = start_local.astimezone(timezone.utc)
    end = end_local.astimezone(timezone.utc)
    report_date = start_local.date()

    try:
        async for session in get_db():
            repo = StatisticsRepository(session)
            service = StatisticsService(repo)
            stats = await service.get_statistics(start, end)
            users_repo = UsersRepository(session)
            user_ids = await users_repo.get_report_recipient_ids(
                settings.REPORT_TELEGRAM_IDS
            )
            break
        else:
            return

        text = "📬 <b>Ежедневный отчёт</b>\n\n" + format_statistics(
            stats, start_local, end_local
        )

        try:
            await asyncio.to_thread(append_daily_stats, stats, report_date)
        except Exception:
            logger.exception("Google Sheets append failed")

        if not user_ids:
            logger.warning("No Telegram report recipients")
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
        hour=settings.REPORT_HOUR,
        minute=settings.REPORT_MINUTE,
        kwargs={"bot": bot},
        id="daily_stats",
        replace_existing=True,
        coalesce=True,
        misfire_grace_time=3600,
    )
    scheduler.start()
    logger.info(
        "Scheduler started: %02d:%02d %s",
        settings.REPORT_HOUR,
        settings.REPORT_MINUTE,
        settings.REPORT_TIMEZONE,
    )
