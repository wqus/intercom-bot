from datetime import datetime, timedelta


def _pct(value: int | float, denominator: int | float) -> float:
    return value / denominator * 100 if denominator else 0.0


def _display_end(end: datetime) -> datetime:
    # Analytics ranges are half-open [start, end). Show the last included moment
    # in human-readable reports instead of the exclusive boundary.
    return end - timedelta(microseconds=1)


def format_statistics(stats: dict, start: datetime, end: datetime) -> str:
    total = int(stats["total"])
    processed = int(stats["processed"])
    escalated = int(stats["escalated"])
    ignored = int(stats.get("ignored", 0))
    results = dict(stats.get("results") or [])
    types = dict(stats.get("request_types") or [])

    shown_end = _display_end(end)

    lines = [
        "📊 <b>Статистика Intercom</b>",
        f"📅 {start:%d.%m.%Y} — {shown_end:%d.%m.%Y}",
        "",
        f"🔹 Всего обращений: <b>{total}</b> (100.0%)",
        f"✅ Обработано: <b>{processed}</b> ({_pct(processed, total):.1f}%)",
        f"⚠️ Эскалировано: <b>{escalated}</b> ({_pct(escalated, total):.1f}%)",
        f"🚫 Игнорировано: <b>{ignored}</b> ({_pct(ignored, total):.1f}%)",
        "",
        "<b>Результаты:</b>",
        f"• Автоматический ответ: {results.get('template', 0)} ({_pct(results.get('template', 0), total):.1f}%)",
        f"• LLM: {results.get('llm', 0)} ({_pct(results.get('llm', 0), total):.1f}%)",
        "",
        "<b>Тип обращения:</b>",
        f"• Диалоги: {types.get('conversation', 0)} ({_pct(types.get('conversation', 0), total):.1f}%)",
        f"• Тикеты: {types.get('ticket', 0)} ({_pct(types.get('ticket', 0), total):.1f}%)",
    ]

    reasons = stats.get("reasons") or []
    if reasons:
        labels = {
            "user_requested_operator": "Запросил оператора",
            "no_category": "Нет категории / система не поняла",
            "attachments": "Вложения",
            "llm_cannot_answer": "LLM не смогла ответить",
            "internal_error": "Внутренняя ошибка",
            "clarification_exhausted": "Исчерпаны уточнения",
            "delivery_failure": "Ошибка доставки",
            "high_risk_refund": "Высокорисковый возврат",
            "high_risk_personal_data": "Персональные данные",
            "high_risk_complaint": "Высокорисковая жалоба",
        }
        lines += ["", "<b>Причины эскалации:</b>"]
        for reason, count in reasons:
            key = getattr(reason, "value", reason)
            lines.append(
                f"• {labels.get(key, key)}: {count} ({_pct(count, escalated):.1f}%)"
            )

    return "\n".join(lines)
