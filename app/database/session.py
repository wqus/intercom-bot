from sqlalchemy.ext.asyncio import async_sessionmaker

from app.database.engine import engine


SessionLocal = async_sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)