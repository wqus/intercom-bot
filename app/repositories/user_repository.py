from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UsersRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert_user(
        self,
        telegram_id: int,
        username: str | None,
        full_name: str | None,
    ) -> User:
        stmt = select(User).where(User.telegram_id == telegram_id)
        result = await self.session.execute(stmt)
        user = result.scalar_one_or_none()

        if user is None:
            user = User(
                telegram_id=telegram_id,
                username=username,
                full_name=full_name,
            )
            self.session.add(user)
        else:
            user.username = username
            user.full_name = full_name

        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def get_all_telegram_ids(self) -> list[int]:
        stmt = select(User.telegram_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())