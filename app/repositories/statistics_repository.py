from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.requests import Request, RequestResult


class StatisticsRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_total_requests(self, start: datetime, end: datetime) -> int:
        stmt = (
            select(func.count())
            .select_from(Request)
            .where(
                Request.created_at >= start,
                Request.created_at <= end,
            )
        )
        return await self.session.scalar(stmt) or 0

    async def get_processed_requests(self, start: datetime, end: datetime) -> int:
        stmt = (
            select(func.count())
            .select_from(Request)
            .where(
                Request.created_at >= start,
                Request.created_at <= end,
                Request.result != RequestResult.ESCALATED,
            )
        )
        return await self.session.scalar(stmt) or 0

    async def get_escalated_requests(self, start: datetime, end: datetime) -> int:
        stmt = (
            select(func.count())
            .select_from(Request)
            .where(
                Request.created_at >= start,
                Request.created_at <= end,
                Request.result == RequestResult.ESCALATED,
            )
        )
        return await self.session.scalar(stmt) or 0

    async def get_escalation_reasons(self, start: datetime, end: datetime):
        stmt = (
            select(Request.escalation_reason, func.count())
            .where(
                Request.created_at >= start,
                Request.created_at <= end,
                Request.result == RequestResult.ESCALATED,
            )
            .group_by(Request.escalation_reason)
            .order_by(func.count().desc())
        )
        result = await self.session.execute(stmt)
        return result.all()

    async def get_request_types(self, start: datetime, end: datetime):
        stmt = (
            select(Request.type, func.count())
            .where(
                Request.created_at >= start,
                Request.created_at <= end,
            )
            .group_by(Request.type)
        )
        result = await self.session.execute(stmt)
        return result.all()

    async def get_results(self, start: datetime, end: datetime):
        stmt = (
            select(Request.result, func.count())
            .where(
                Request.created_at >= start,
                Request.created_at <= end,
            )
            .group_by(Request.result)
        )
        result = await self.session.execute(stmt)
        return result.all()