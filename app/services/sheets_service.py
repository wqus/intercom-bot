from datetime import date
import time
from typing import Any

import gspread
from google.oauth2.service_account import Credentials

from app.core.config import settings

import logging

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# One row per calendar day. Every count has a percentage column. Percentages
# use the natural denominator documented in ``stats_to_row``.
HEADERS = [
    "date",
    "total",
    "processed",
    "escalated",
    "processed_pct",
    "escalated_pct",
    "result_template",
    "result_template_pct",
    "result_llm",
    "result_llm_pct",
    "result_ignored",
    "result_ignored_pct",
    "type_conversation",
    "type_conversation_pct",
    "type_ticket",
    "type_ticket_pct",
    "reason_operator",
    "reason_operator_pct",
    "reason_no_category",
    "reason_no_category_pct",
    "reason_attachments",
    "reason_attachments_pct",
    "reason_llm",
    "reason_llm_pct",
    "reason_internal",
    "reason_internal_pct",
]

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
        # High-risk paths are intentionally grouped into the same public
        # reporting bucket as "no category" for now. This keeps the sheet
        # compact while preserving the fact that the event was escalated.
        "high_risk_refund": "reason_no_category",
        "high_risk_personal_data": "reason_no_category",
        "high_risk_complaint": "reason_no_category",
        "attachments": "reason_attachments",
        "llm_cannot_answer": "reason_llm",
        "internal_error": "reason_internal",
    }
    return _count_by_key(stats.get("reasons") or [], mapping)


def stats_to_row(stats: dict[str, Any], report_date: date) -> list:
    total = int(stats.get("total", 0))
    processed = int(stats.get("processed", 0))
    escalated = int(stats.get("escalated", 0))

    # Top-3 is an automatic response and is intentionally grouped into the
    # single ``result_template`` business category. The report does not expose
    # Top-3 as a separate metric.
    result_template = 0
    result_llm = 0
    result_ignored = int(stats.get("ignored", 0))
    for key, count in stats.get("results") or []:
        if key in {"template", "top3"}:
            result_template += int(count)
        elif key == "llm":
            result_llm += int(count)
        elif key == "ignored":
            result_ignored = int(count)

    types = {
        "type_conversation": 0,
        "type_ticket": 0,
    }
    for key, count in stats.get("request_types") or []:
        if key in types:
            types[key] = int(count)

    reasons = _reason_values(stats)
    escalation_den = escalated

    row = {
        "date": report_date.isoformat(),
        "total": total,
        "processed": processed,
        "escalated": escalated,
        "processed_pct": _pct(processed, total),
        "escalated_pct": _pct(escalated, total),
        "result_template": result_template,
        "result_template_pct": _pct(result_template, total),
        "result_llm": result_llm,
        "result_llm_pct": _pct(result_llm, total),
        "result_ignored": result_ignored,
        "result_ignored_pct": _pct(result_ignored, total),
        "type_conversation": types["type_conversation"],
        "type_conversation_pct": _pct(types["type_conversation"], total),
        "type_ticket": types["type_ticket"],
        "type_ticket_pct": _pct(types["type_ticket"], total),
        "reason_operator": reasons["reason_operator"],
        "reason_operator_pct": _pct(reasons["reason_operator"], escalation_den),
        "reason_no_category": reasons["reason_no_category"],
        "reason_no_category_pct": _pct(reasons["reason_no_category"], escalation_den),
        "reason_attachments": reasons["reason_attachments"],
        "reason_attachments_pct": _pct(reasons["reason_attachments"], escalation_den),
        "reason_llm": reasons["reason_llm"],
        "reason_llm_pct": _pct(reasons["reason_llm"], escalation_den),
        "reason_internal": reasons["reason_internal"],
        "reason_internal_pct": _pct(reasons["reason_internal"], escalation_den),
    }
    return [row[h] for h in HEADERS]


def _col_letter(index: int) -> str:
    result = ""
    while index:
        index, rem = divmod(index - 1, 26)
        result = chr(65 + rem) + result
    return result


def _ensure_headers(ws, existing: list[list[str]]) -> list[list[str]]:
    """Migrate an existing sheet by column name, preserving historical values."""
    if not existing:
        ws.update(
            "A1:" + _col_letter(len(HEADERS)) + "1",
            [HEADERS],
            value_input_option="USER_ENTERED",
        )
        return [HEADERS]

    current = existing[0]
    if current == HEADERS:
        return existing

    old_index = {name: idx for idx, name in enumerate(current)}
    migrated = [HEADERS]
    for old_row in existing[1:]:
        migrated.append([
            old_row[old_index[h]] if h in old_index and old_index[h] < len(old_row) else ""
            for h in HEADERS
        ])

    end_col = _col_letter(len(HEADERS))
    ws.update(
        f"A1:{end_col}{len(migrated)}",
        migrated,
        value_input_option="USER_ENTERED",
    )

    # Explicitly clear columns removed from the reporting contract. Updating a
    # shorter range does not delete old cells in Google Sheets, so without
    # this cleanup deprecated columns would remain visible after migration.
    if len(current) > len(HEADERS):
        old_end_col = _col_letter(len(current))
        ws.batch_clear([f"{_col_letter(len(HEADERS) + 1)}1:{old_end_col}{len(existing)}"])

    logger.info("Google Sheet headers migrated: %d -> %d columns", len(current), len(HEADERS))
    return migrated


def _get_worksheet():
    creds = Credentials.from_service_account_file(
        settings.GOOGLE_CREDENTIALS_PATH,
        scopes=SCOPES,
    )
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(settings.GOOGLE_SHEET_ID)
    return spreadsheet.worksheet(settings.GOOGLE_SHEET_WORKSHEET)


RETRYABLE_GOOGLE_STATUS_CODES = {429, 500, 502, 503, 504}
SHEETS_MAX_ATTEMPTS = 4
SHEETS_RETRY_DELAYS_SECONDS = (1.0, 3.0, 8.0)


def _is_retryable_google_error(exc: Exception) -> bool:
    """Retry only transient Google API failures; never hide auth/config errors."""
    if not isinstance(exc, gspread.exceptions.APIError):
        return False
    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", None)
    if status_code in RETRYABLE_GOOGLE_STATUS_CODES:
        return True
    # gspread versions can expose the status as ``code`` instead of
    # ``status_code`` on the response object.
    return getattr(response, "code", None) in RETRYABLE_GOOGLE_STATUS_CODES


def _append_daily_stats_once(stats: dict[str, Any], report_date: date) -> None:
    ws = _get_worksheet()
    existing = _ensure_headers(ws, ws.get_all_values())
    row = stats_to_row(stats, report_date)
    end_col = _col_letter(len(HEADERS))

    # Idempotent by report date: a retry updates the same row rather than
    # creating duplicates.
    target_date = report_date.isoformat()
    for idx, values in enumerate(existing[1:], start=2):
        if values and values[0] == target_date:
            ws.update(
                f"A{idx}:{end_col}{idx}",
                [row],
                value_input_option="USER_ENTERED",
            )
            logger.info("Daily stats updated in Google Sheets for %s", report_date)
            return

    ws.append_row(row, value_input_option="USER_ENTERED")
    logger.info("Daily stats appended to Google Sheets for %s", report_date)


def append_daily_stats(stats: dict[str, Any], report_date: date) -> None:
    if not settings.GOOGLE_SHEET_ID:
        logger.warning("GOOGLE_SHEET_ID is empty; skipping Google Sheets")
        return

    last_error: Exception | None = None
    for attempt in range(1, SHEETS_MAX_ATTEMPTS + 1):
        try:
            _append_daily_stats_once(stats, report_date)
            return
        except Exception as exc:
            last_error = exc
            if not _is_retryable_google_error(exc) or attempt >= SHEETS_MAX_ATTEMPTS:
                raise
            delay = SHEETS_RETRY_DELAYS_SECONDS[attempt - 1]
            logger.warning(
                "Transient Google Sheets error (attempt %d/%d); retrying in %.1fs: %s",
                attempt,
                SHEETS_MAX_ATTEMPTS,
                delay,
                exc,
            )
            time.sleep(delay)

    # Defensive: the loop either returns or raises above.
    if last_error is not None:
        raise last_error
