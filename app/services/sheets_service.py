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
    "result_template",
    "result_llm",
    "result_ignored",
    "type_conversation",
    "type_ticket",
    "reason_operator",
    "reason_no_category",
    "reason_attachments",
    "reason_llm",
    "reason_wants_new_school",
    "reason_internal",
]


def _get_worksheet():
    creds = Credentials.from_service_account_file(
        settings.GOOGLE_CREDENTIALS_PATH,
        scopes=SCOPES,
    )
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(settings.GOOGLE_SHEET_ID)
    return spreadsheet.worksheet(settings.GOOGLE_SHEET_WORKSHEET)


def _count_by_key(rows: list, mapping: dict) -> dict[str, int]:
    result = {col: 0 for col in mapping.values()}
    for item, count in rows:
        col = mapping.get(item)
        if col is not None:
            result[col] = result.get(col, 0) + count
    return result

def stats_to_row(stats: dict[str, Any], report_date: date) -> list:
    total = stats["total"]
    processed = stats["processed"]
    escalated = stats["escalated"]
    processed_pct = round(processed / total * 100, 1) if total else 0.0
    escalated_pct = round(escalated / total * 100, 1) if total else 0.0

    result_map = {
        RequestResult.TEMPLATE: "result_template",
        RequestResult.LLM: "result_llm",
        RequestResult.IGNORED: "result_ignored",
    }
    type_map = {
        RequestType.CONVERSATION: "type_conversation",
        RequestType.TICKET: "type_ticket",
    }
    reason_map = {
        EscalationReason.USER_REQUESTED_OPERATOR: "reason_operator",
        EscalationReason.NO_CATEGORY: "reason_no_category",
        EscalationReason.ATTACHMENTS: "reason_attachments",
        EscalationReason.LLM_CANNOT_ANSWER: "reason_llm",
        EscalationReason.WANTS_NEW_SCHOOL: "reason_wants_new_school",
        EscalationReason.INTERNAL_ERROR: "reason_internal",
    }
    results = _count_by_key(stats.get("results") or [], result_map)
    types = _count_by_key(stats.get("request_types") or [], type_map)
    reasons = _count_by_key(stats.get("reasons") or [], reason_map)

    row_dict = {
        "date": report_date.isoformat(),
        "total": total,
        "processed": processed,
        "escalated": escalated,
        "processed_pct": processed_pct,
        "escalated_pct": escalated_pct,

        "result_template": results.get("result_template", 0),
        "result_llm": results.get("result_llm", 0),
        "result_ignored": results.get("result_ignored", 0),

        "type_conversation": types.get("type_conversation", 0),
        "type_ticket": types.get("type_ticket", 0),

        "reason_operator": reasons.get("reason_operator", 0),
        "reason_no_category": reasons.get("reason_no_category", 0),
        "reason_attachments": reasons.get("reason_attachments", 0),
        "reason_llm": reasons.get("reason_llm", 0),
        "reason_wants_new_school": reasons.get("reason_wants_new_school", 0),
        "reason_internal": reasons.get("reason_internal", 0),
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