from aiogram.fsm.state import State, StatesGroup


class StatisticsPeriod(StatesGroup):
    waiting_start = State()
    waiting_end = State()