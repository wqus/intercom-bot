import logging
from datetime import date
from typing import Any

import gspread
from google.oauth2.service_account import Credentials

from app.core.config import settings
from app.models.requests import EscalationReason, RequestResult, RequestType

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

HEADERS = [
    "date",
    "total",
    "processed",
    "escalated",
    "processed_pct",
    "escalated_pct",
    "template",
    "llm",
    "conversation",
    "ticket",
    "reason_operator",
    "reason_no_category",
    "reason_attachments",
    "reason_llm",
    "reason_internal",
    "reason_unknown",
]


def _get_worksheet():
    creds = Credentials.from_service_account_file(
        settings.GOOGLE_CREDENTIALS_PATH,
        scopes=SCOPES,
    )
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(settings.GOOGLE_SHEET_ID)
    return spreadsheet.worksheet(settings.GOOGLE_SHEET_WORKSHEET)


def _normalize(item, enum_cls):
    """Enum | name | value → Enum member."""
    if item is None:
        return None
    if isinstance(item, enum_cls):
        return item
    if isinstance(item, str):
        if item in enum_cls.__members__:
            return enum_cls[item]
        try:
            return enum_cls(item)
        except ValueError:
            return None
    return None


def _count_by_key(
    rows: list,
    enum_cls,
    mapping: dict,
) -> tuple[dict[str, int], int]:
    result = {col: 0 for col in mapping.values()}
    unknown = 0

    for item, count in rows:
        member = _normalize(item, enum_cls)
        if member is None:
            unknown += count
            continue
        col = mapping.get(member)
        if col is None:
            unknown += count
        else:
            result[col] = result.get(col, 0) + count

    return result, unknown


def stats_to_row(stats: dict[str, Any], report_date: date) -> list:
    total = stats["total"]
    processed = stats["processed"]
    escalated = stats["escalated"]
    processed_pct = round(processed / total * 100, 1) if total else 0.0
    escalated_pct = round(escalated / total * 100, 1) if total else 0.0

    result_map = {
        RequestResult.TEMPLATE: "template",
        RequestResult.LLM: "llm",
        RequestResult.ESCALATED: "escalated",
    }
    type_map = {
        RequestType.CONVERSATION: "conversation",
        RequestType.TICKET: "ticket",
    }
    reason_map = {
        EscalationReason.USER_REQUESTED_OPERATOR: "reason_operator",
        EscalationReason.NO_CATEGORY: "reason_no_category",
        EscalationReason.ATTACHMENTS: "reason_attachments",
        EscalationReason.LLM_CANNOT_ANSWER: "reason_llm",
        EscalationReason.INTERNAL_ERROR: "reason_internal",
    }

    results, _ = _count_by_key(
        stats.get("results") or [], RequestResult, result_map
    )
    types, _ = _count_by_key(
        stats.get("request_types") or [], RequestType, type_map
    )
    reasons, reason_unknown = _count_by_key(
        stats.get("reasons") or [], EscalationReason, reason_map
    )

    row_dict = {
        "date": report_date.isoformat(),
        "total": total,
        "processed": processed,
        "escalated": escalated,
        "processed_pct": processed_pct,
        "escalated_pct": escalated_pct,
        "template": results.get("template", 0),
        "llm": results.get("llm", 0),
        "conversation": types.get("conversation", 0),
        "ticket": types.get("ticket", 0),
        "reason_operator": reasons.get("reason_operator", 0),
        "reason_no_category": reasons.get("reason_no_category", 0),
        "reason_attachments": reasons.get("reason_attachments", 0),
        "reason_llm": reasons.get("reason_llm", 0),
        "reason_internal": reasons.get("reason_internal", 0),
        "reason_unknown": reason_unknown,
    }
    return [row_dict[h] for h in HEADERS]


def append_daily_stats(stats: dict[str, Any], report_date: date) -> None:
    ws = _get_worksheet()

    existing = ws.get_all_values()
    if not existing:
        ws.append_row(HEADERS, value_input_option="USER_ENTERED")

    row = stats_to_row(stats, report_date)
    ws.append_row(row, value_input_option="USER_ENTERED")
    logger.info("Daily stats appended to Google Sheet for %s", report_date)