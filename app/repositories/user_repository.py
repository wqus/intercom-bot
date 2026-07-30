from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
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
        stmt = insert(User).values(
            telegram_id=telegram_id,
            username=username,
            full_name=full_name,
        ).on_conflict_do_update(
            index_elements=["telegram_id"],
            set_={
                "username": username,
                "full_name": full_name,
            }
        ).returning(User)

        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.scalar_one()

    async def get_all_telegram_ids(self) -> list[int]:
        stmt = select(User.telegram_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())