from datetime import datetime
from typing import Any

from app.models.requests import EscalationReason, RequestResult, RequestType

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


def format_statistics(
    stats: dict[str, Any],
    start: datetime,
    end: datetime,
) -> str:
    total = stats["total"]
    processed = stats["processed"]
    escalated = stats["escalated"]

    header = (
        "📊 <b>Статистика</b>\n"
        f"📅 {start.strftime('%d.%m.%Y %H:%M')} — {end.strftime('%d.%m.%Y %H:%M')}"
    )

    if total == 0:
        return f"{header}\n\nЗа этот период обращений нет."

    processed_pct = processed / total * 100
    escalated_pct = escalated / total * 100

    lines = [
        header,
        "",
        f"🔹 Всего: <b>{total}</b>",
        f"✅ Обработано: <b>{processed}</b> ({processed_pct:.1f}%)",
        f"⚠️ Эскалировано: <b>{escalated}</b> ({escalated_pct:.1f}%)",
    ]

    results = stats.get("results") or []
    if results:
        lines.append("")
        lines.append("<b>По результату:</b>")
        for result, count in results:
            label = RESULT_LABELS.get(result, str(result))
            lines.append(f"• {label}: {count}")

    reasons = stats.get("reasons") or []
    if reasons:
        lines.append("")
        lines.append("<b>Причины эскалации:</b>")
        for reason, count in reasons:
            if reason is None:
                label = "Не указана"
            else:
                label = REASON_LABELS.get(reason, str(reason))
            lines.append(f"• {label}: {count}")

    request_types = stats.get("request_types") or []
    if request_types:
        lines.append("")
        lines.append("<b>Типы обращений:</b>")
        for rtype, count in request_types:
            label = TYPE_LABELS.get(rtype, str(rtype))
            lines.append(f"• {label}: {count}")

    return "\n".join(lines)