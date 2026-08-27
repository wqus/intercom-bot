from datetime import datetime

from app.repositories.statistics_repository import StatisticsRepository


class StatisticsService:
    def __init__(self, repository: StatisticsRepository):
        self.repository = repository

    async def get_statistics(self, start: datetime, end: datetime) -> dict:
        total = await self.repository.get_total_requests(start, end)
        result_counts = await self.repository.get_result_counts(start, end)
        with_interaction = result_counts["with_interaction"]
        escalated = await self.repository.get_escalated_events(start, end)

        # A state-driven escalation can exist without a support_interaction row.
        # Processed therefore means: interacted with, but not escalated.
        processed = max(0, with_interaction - escalated)

        return {
            "total": total,
            "processed": processed,
            "escalated": escalated,
            "with_interaction": with_interaction,
            "automated": result_counts["automated"],
            "llm_used": result_counts["llm_used"],
            "results": [
                ("template", result_counts["template"]),
                ("llm", result_counts["llm"]),
                ("ignored", result_counts["ignored"]),
            ],
            "reasons": await self.repository.get_escalation_reasons(start, end),
            "request_types": await self.repository.get_request_types(start, end),
        }
