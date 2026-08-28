from datetime import datetime, timedelta

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.core.dependencies import get_db
from app.keyboards.statistics import (
    cancel_keyboard,
    period_keyboard,
    statistics_keyboard,
)
from app.repositories.statistics_repository import StatisticsRepository
from app.services.statistics_service import StatisticsService
from app.states.statistics import StatisticsPeriod
from app.utils.formatter import format_statistics
from app.utils.parser import parse_date
from app.utils.periods import (
    get_month_range,
    get_today_range,
    get_week_range,
    get_yesterday_range,
)

router = Router()


async def _send_stats(message: Message, start: datetime, end: datetime) -> None:
    async for session in get_db():
        repo = StatisticsRepository(session)
        service = StatisticsService(repo)
        stats = await service.get_statistics(start, end)
        text = format_statistics(stats, start, end)
        await message.answer(text, reply_markup=period_keyboard)
        break


@router.message(F.text == "Статистика")
async def statistics_menu(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Выберите период.", reply_markup=period_keyboard)


@router.message(F.text == "◀️ Назад")
async def back_to_main(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Главное меню.", reply_markup=statistics_keyboard)


@router.message(F.text == "Отмена")
async def cancel_period(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Выберите период.", reply_markup=period_keyboard)


@router.message(F.text == "Сегодня")
async def stats_today(message: Message, state: FSMContext):
    await state.clear()
    start, end = get_today_range()
    await _send_stats(message, start, end)


@router.message(F.text == "Вчера")
async def stats_yesterday(message: Message, state: FSMContext):
    await state.clear()
    start, end = get_yesterday_range()
    await _send_stats(message, start, end)


@router.message(F.text == "Неделя")
async def stats_week(message: Message, state: FSMContext):
    await state.clear()
    start, end = get_week_range()
    await _send_stats(message, start, end)


@router.message(F.text == "Месяц")
async def stats_month(message: Message, state: FSMContext):
    await state.clear()
    start, end = get_month_range()
    await _send_stats(message, start, end)


@router.message(F.text == "Свой период")
async def custom_period_start(message: Message, state: FSMContext):
    await state.set_state(StatisticsPeriod.waiting_start)
    await message.answer(
        "Введите дату <b>начала</b> периода.\n"
        "Формат: <code>29.07.2026</code> или <code>29.07.2026 17:00</code>",
        reply_markup=cancel_keyboard,
    )


@router.message(StatisticsPeriod.waiting_start)
async def custom_period_start_date(message: Message, state: FSMContext):
    start = parse_date(message.text or "")
    if start is None:
        await message.answer(
            "Не понял дату. Пример: <code>29.07.2026</code> или <code>29.07.2026 17:00</code>"
        )
        return

    await state.update_data(start=start.isoformat())
    await state.set_state(StatisticsPeriod.waiting_end)
    await message.answer(
        "Введите дату <b>конца</b> периода.\n"
        "Формат: <code>30.07.2026</code> или <code>30.07.2026 23:59</code>",
        reply_markup=cancel_keyboard,
    )


@router.message(StatisticsPeriod.waiting_end)
async def custom_period_end_date(message: Message, state: FSMContext):
    raw_end = (message.text or "").strip()
    end = parse_date(raw_end)
    if end is None:
        await message.answer(
            "Не понял дату. Пример: <code>30.07.2026</code> или <code>30.07.2026 23:59</code>"
        )
        return

    # Date-only end is inclusive for the Telegram UI, so convert it to the
    # exclusive next-day midnight used by repository queries.
    if " " not in raw_end:
        end = end + timedelta(days=1)

    data = await state.get_data()
    start = datetime.fromisoformat(data["start"])

    if start > end:
        await message.answer(
            "Дата начала позже конца. Введите дату конца ещё раз."
        )
        return

    await state.clear()
    await _send_stats(message, start, end)