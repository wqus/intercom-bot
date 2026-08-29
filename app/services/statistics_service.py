from datetime import datetime

from app.repositories.statistics_repository import StatisticsRepository


class StatisticsService:
    def __init__(self, repository: StatisticsRepository):
        self.repository = repository

    async def get_statistics(self, start: datetime, end: datetime) -> dict:
        result_counts = await self.repository.get_result_counts(start, end)

        return {
            "total": result_counts["total"],
            "processed": result_counts["processed"],
            "escalated": result_counts["escalated"],
            "ignored": result_counts["ignored"],
            "with_interaction": result_counts["with_interaction"],
            "automated": result_counts["automated"],
            "llm_used": result_counts["llm_used"],
            "results": [
                ("template", result_counts["template"]),
                ("llm", result_counts["llm"]),
                ("escalated", result_counts["escalated"]),
                ("ignored", result_counts["ignored"]),
            ],
            "reasons": await self.repository.get_escalation_reasons(start, end),
            "request_types": await self.repository.get_request_types(start, end),
        }
