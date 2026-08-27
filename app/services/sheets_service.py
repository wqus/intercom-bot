import logging
from datetime import date
from typing import Any

import gspread
from google.oauth2.service_account import Credentials

from app.core.config import settings

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# The sheet is intentionally flat (one row = one calendar day), but every
# quantitative count has a paired percentage column. Percentages are scoped to
# the section's natural denominator and are documented in the header names.
HEADERS = [
    "date",

    # Overall / denominator
    "total_requests",
    "total_requests_pct",

    # Processing status: % of all inbound requests
    "processed",
    "processed_pct",
    "escalated",
    "escalated_pct",
    "with_interaction",
    "with_interaction_pct",
    "without_interaction",
    "without_interaction_pct",

    # Pipeline result: counts + % of processed non-escalated requests
    "result_template",
    "result_template_pct",
    "result_llm",
    "result_llm_pct",
    "result_ignored",
    "result_ignored_pct",

    # Request type: counts + % of all inbound requests
    "type_conversation",
    "type_conversation_pct",
    "type_ticket",
    "type_ticket_pct",
    "type_other",
    "type_other_pct",

    # Automation flags: counts + % of interactions
    "automated",
    "automated_pct",
    "llm_used",
    "llm_used_pct",

    # Escalation reasons: counts + % of escalations
    "reason_operator",
    "reason_operator_pct",
    "reason_no_category",
    "reason_no_category_pct",
    "reason_attachments",
    "reason_attachments_pct",
    "reason_llm",
    "reason_llm_pct",
    "reason_wants_new_school",
    "reason_wants_new_school_pct",
    "reason_internal",
    "reason_internal_pct",
    "reason_llm_noise",
    "reason_llm_noise_pct",
    # Kept for compatibility with versions where these reasons existed.
    "reason_clarification_exhausted",
    "reason_clarification_exhausted_pct",
    "reason_delivery_failure",
    "reason_delivery_failure_pct",
    "reason_high_risk_refund",
    "reason_high_risk_refund_pct",
    "reason_high_risk_personal_data",
    "reason_high_risk_personal_data_pct",
    "reason_high_risk_complaint",
    "reason_high_risk_complaint_pct",
    "reason_other",
    "reason_other_pct",
]

COUNT_HEADERS = [
    h for h in HEADERS
    if h != "date" and not h.endswith("_pct")
]


def _get_worksheet():
    creds = Credentials.from_service_account_file(
        settings.GOOGLE_CREDENTIALS_PATH,
        scopes=SCOPES,
    )
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(settings.GOOGLE_SHEET_ID)
    return spreadsheet.worksheet(settings.GOOGLE_SHEET_WORKSHEET)


def _pct(value: int | float, denominator: int | float) -> float:
    return round(float(value) / float(denominator) * 100, 1) if denominator else 0.0


def _count_by_key(rows, mapping):
    result = {col: 0 for col in mapping.values()}
    for item, count in rows:
        key = getattr(item, "value", item)
        col = mapping.get(key)
        if col:
            result[col] = int(count)
    return result


def _reason_values(stats: dict[str, Any]) -> dict[str, int]:
    mapping = {
        "user_requested_operator": "reason_operator",
        "no_category": "reason_no_category",
        "attachments": "reason_attachments",
        "llm_cannot_answer": "reason_llm",
        "wants_new_school": "reason_wants_new_school",
        "internal_error": "reason_internal",
        "llm_noise": "reason_llm_noise",
        # Compatibility with earlier/alternate enum values.
        "clarification_exhausted": "reason_clarification_exhausted",
        "delivery_failure": "reason_delivery_failure",
        "high_risk_refund": "reason_high_risk_refund",
        "high_risk_personal_data": "reason_high_risk_personal_data",
        "high_risk_complaint": "reason_high_risk_complaint",
    }
    result = _count_by_key(stats.get("reasons") or [], mapping)
    known = set(mapping)
    result["reason_other"] = 0
    for item, count in stats.get("reasons") or []:
        key = getattr(item, "value", item)
        if key not in known:
            result["reason_other"] += int(count)
    return result


def stats_to_row(stats: dict[str, Any], report_date: date) -> list:
    total = int(stats.get("total", 0))
    processed = int(stats.get("processed", 0))
    escalated = int(stats.get("escalated", 0))
    with_interaction = int(stats.get("with_interaction", 0))
    without_interaction = max(0, total - with_interaction)

    results = {"result_template": 0, "result_llm": 0, "result_ignored": 0}
    for key, count in stats.get("results") or []:
        if key in {"template", "llm", "ignored"}:
            results[f"result_{key}"] = int(count)

    # request_type values are based on inbound_events, so the denominator is total.
    types = {
        "type_conversation": 0,
        "type_ticket": 0,
        "type_other": 0,
    }
    for key, count in stats.get("request_types") or []:
        if key in {"conversation", "ticket", "other"}:
            types[f"type_{key}"] = int(count)

    reasons = _reason_values(stats)
    automated = int(stats.get("automated", 0))
    llm_used = int(stats.get("llm_used", 0))

    row = {
        "date": report_date.isoformat(),
        "total_requests": total,
        "total_requests_pct": 100.0,
        "processed": processed,
        "processed_pct": _pct(processed, total),
        "escalated": escalated,
        "escalated_pct": _pct(escalated, total),
        "with_interaction": with_interaction,
        "with_interaction_pct": _pct(with_interaction, total),
        "without_interaction": without_interaction,
        "without_interaction_pct": _pct(without_interaction, total),

        "result_template": results["result_template"],
        "result_template_pct": _pct(results["result_template"], processed),
        "result_llm": results["result_llm"],
        "result_llm_pct": _pct(results["result_llm"], processed),
        "result_ignored": results["result_ignored"],
        "result_ignored_pct": _pct(results["result_ignored"], processed),

        "type_conversation": types["type_conversation"],
        "type_conversation_pct": _pct(types["type_conversation"], total),
        "type_ticket": types["type_ticket"],
        "type_ticket_pct": _pct(types["type_ticket"], total),
        "type_other": types["type_other"],
        "type_other_pct": _pct(types["type_other"], total),

        "automated": automated,
        "automated_pct": _pct(automated, with_interaction),
        "llm_used": llm_used,
        "llm_used_pct": _pct(llm_used, with_interaction),
    }

    for count_col in [h for h in HEADERS if h.startswith("reason_") and not h.endswith("_pct")]:
        count = reasons.get(count_col, 0)
        row[count_col] = count
        row[f"{count_col}_pct"] = _pct(count, escalated)

    return [row[h] for h in HEADERS]


def _col_letter(index: int) -> str:
    result = ""
    while index:
        index, rem = divmod(index - 1, 26)
        result = chr(65 + rem) + result
    return result


def _ensure_headers(ws, existing: list[list[str]]) -> list[list[str]]:
    """Migrate an existing sheet header without destroying historical data."""
    if not existing:
        ws.update("A1:" + _col_letter(len(HEADERS)) + "1", [HEADERS], value_input_option="USER_ENTERED")
        return [HEADERS]

    current = existing[0]
    if current == HEADERS:
        return existing

    # Preserve old columns by name, then append new columns at the end.
    old_index = {name: idx for idx, name in enumerate(current)}
    migrated = [HEADERS]
    for old_row in existing[1:]:
        migrated.append([
            old_row[old_index[h]] if h in old_index and old_index[h] < len(old_row) else ""
            for h in HEADERS
        ])

    end_col = _col_letter(len(HEADERS))
    if len(migrated) > 1:
        ws.update(f"A1:{end_col}{len(migrated)}", migrated, value_input_option="USER_ENTERED")
    else:
        ws.update(f"A1:{end_col}1", [HEADERS], value_input_option="USER_ENTERED")
    logger.info("Google Sheet headers migrated: %d -> %d columns", len(current), len(HEADERS))
    return migrated


def append_daily_stats(stats: dict[str, Any], report_date: date) -> None:
    if not settings.GOOGLE_SHEET_ID:
        logger.warning("GOOGLE_SHEET_ID is empty; skipping Google Sheets")
        return

    ws = _get_worksheet()
    existing = _ensure_headers(ws, ws.get_all_values())
    row = stats_to_row(stats, report_date)
    end_col = _col_letter(len(HEADERS))

    # Idempotent by report date: retries update the same daily row.
    for idx, values in enumerate(existing[1:], start=2):
        if values and values[0] == report_date.isoformat():
            ws.update(f"A{idx}:{end_col}{idx}", [row], value_input_option="USER_ENTERED")
            logger.info("Daily stats updated in Google Sheets for %s", report_date)
            return

    ws.append_row(row, value_input_option="USER_ENTERED")
    logger.info("Daily stats appended to Google Sheets for %s", report_date)
