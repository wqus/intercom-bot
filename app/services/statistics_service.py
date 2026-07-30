from datetime import datetime

from app.repositories.statistics_repository import StatisticsRepository


class StatisticsService:
    def __init__(self, repository: StatisticsRepository):
        self.repository = repository

    async def get_statistics(self, start: datetime, end: datetime) -> dict:
        return {
            "total": await self.repository.get_total_requests(start, end),
            "processed": await self.repository.get_processed_requests(start, end),
            "escalated": await self.repository.get_escalated_requests(start, end),
            "reasons": await self.repository.get_escalation_reasons(start, end),
            "request_types": await self.repository.get_request_types(start, end),
            "results": await self.repository.get_results(start, end),
        }