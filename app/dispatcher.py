from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from app.handlers.start import router as start_router
from app.handlers.statistics import router as statistics_router

dp = Dispatcher(storage=MemoryStorage())

dp.include_router(start_router)
dp.include_router(statistics_router)