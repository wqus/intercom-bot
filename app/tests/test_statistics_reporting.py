import pytest
from datetime import date

from app.services.sheets_service import HEADERS, stats_to_row
from app.services.statistics_service import StatisticsService


def test_sheet_headers_match_requested_core_columns():
    expected_prefix = [
        "date", "total", "processed", "escalated", "processed_pct",
        "escalated_pct", "result_template", "result_template_pct",
        "result_llm", "result_llm_pct", "result_ignored", "result_ignored_pct",
        "type_conversation", "type_conversation_pct",
        "type_ticket", "type_ticket_pct",
        "reason_operator", "reason_operator_pct",
        "reason_no_category", "reason_no_category_pct",
        "reason_attachments", "reason_attachments_pct",
        "reason_llm", "reason_llm_pct",
        "reason_internal", "reason_internal_pct",
    ]
    assert HEADERS[:len(expected_prefix)] == expected_prefix
    assert len(HEADERS) == len(set(HEADERS))


def test_sheet_percentages_use_total_and_escalations():
    stats = {
        "total": 200,
        "processed": 150,
        "escalated": 40,
        "ignored": 5,
        "unprocessed": 5,
        "results": [("template", 90), ("top3", 50), ("llm", 10), ("ignored", 5)],
        "request_types": [("conversation", 150), ("ticket", 50)],
        "reasons": [
            ("user_requested_operator", 20),
            ("no_category", 10),
            ("attachments", 5),
            ("llm_cannot_answer", 2),
            ("internal_error", 1),
            ("high_risk_refund", 1),
        ],
    }
    row = dict(zip(HEADERS, stats_to_row(stats, date(2026, 8, 27))))
    assert row["processed_pct"] == 75.0
    assert row["escalated_pct"] == 20.0
    assert row["result_automatic_response"] == 140
    assert row["result_automatic_response_pct"] == 70.0
    assert row["result_top3_pct"] == 25.0
    assert row["result_ignored_pct"] == 2.5
    assert row["reason_operator_pct"] == 50.0
    assert row["reason_no_category_pct"] == 25.0
    assert row["reason_other"] == 1
    assert "reason_wants_new_school" not in HEADERS


@pytest.mark.asyncio
async def test_statistics_service_uses_event_level_result_counts():
    class FakeRepo:
        async def get_result_counts(self, start, end):
            return {
                "total": 10, "processed": 6, "escalated": 2, "ignored": 1,
                "unprocessed": 1, "with_interaction": 8, "automated": 6,
                "llm_used": 0, "template": 4, "top3": 2, "llm": 0,
                "automatic_response": 6,
            }

        async def get_escalation_reasons(self, start, end):
            return [("no_category", 2)]

        async def get_request_types(self, start, end):
            return [("conversation", 8), ("ticket", 2)]

    service = StatisticsService(FakeRepo())
    result = await service.get_statistics(None, None)
    assert result["total"] == 10
    assert result["processed"] == 6
    assert result["escalated"] == 2
    assert dict(result["results"]) == {
        "template": 4, "top3": 2, "llm": 0, "ignored": 1
    }


def test_stats_row_has_no_wants_new_school_reason_columns():
    stats = {
        "total": 10, "processed": 2, "escalated": 3, "ignored": 1, "unprocessed": 4,
        "results": [], "request_types": [],
        "reasons": [("wants_new_school", 2)],
    }
    row = dict(zip(HEADERS, stats_to_row(stats, date(2026, 8, 27))))
    assert "reason_wants_new_school" not in row
    assert row["reason_other"] == 2
