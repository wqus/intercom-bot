from datetime import datetime

from app.models.requests import RequestResult, RequestType, EscalationReason
from app.repositories.statistics_repository import StatisticsRepository


RESULT_LABELS = {
    RequestResult.TEMPLATE: "Шаблон",
    RequestResult.LLM: "LLM",
    RequestResult.ESCALATED: "Эскалация",
    RequestResult.IGNORED: "Игнор",
}

TYPE_LABELS = {
    RequestType.CONVERSATION: "Диалог",
    RequestType.TICKET: "Тикет",
}

REASON_LABELS = {
    EscalationReason.USER_REQUESTED_OPERATOR: "Запросил оператора",
    EscalationReason.NO_CATEGORY: "Нет категории",
    EscalationReason.LLM_CANNOT_ANSWER: "LLM не смогла ответить",
    EscalationReason.INTERNAL_ERROR: "Внутренняя ошибка",
    EscalationReason.WANTS_NEW_SCHOOL: "Хочет в новую школу",
    EscalationReason.ATTACHMENTS: "Есть вложения",
}


class StatisticsService:
    def __init__(self, repository: StatisticsRepository):
        self.repository = repository

    async def get_statistics(self, start: datetime, end: datetime) -> dict:
        results_raw = await self.repository.get_results(start, end)
        types_raw = await self.repository.get_request_types(start, end)
        reasons_raw = await self.repository.get_escalation_reasons(start, end)

        return {
            "total": await self.repository.get_total_requests(start, end),
            "processed": await self.repository.get_processed_requests(start, end),
            "escalated": await self.repository.get_escalated_requests(start, end),
            "results": [
                {
                    "name": RESULT_LABELS.get(result, str(result)),
                    "count": count,
                }
                for result, count in results_raw
            ],
            "request_types": [
                {
                    "name": TYPE_LABELS.get(req_type, str(req_type)),
                    "count": count,
                }
                for req_type, count in types_raw
            ],
            "reasons": [
                {
                    "name": REASON_LABELS.get(reason, str(reason) if reason else "Не указана"),
                    "count": count,
                }
                for reason, count in reasons_raw
            ],
        }