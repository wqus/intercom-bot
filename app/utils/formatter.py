from datetime import datetime


def _pct(value: int | float, denominator: int | float) -> float:
    return value / denominator * 100 if denominator else 0.0


def format_statistics(stats: dict, start: datetime, end: datetime) -> str:
    total = stats["total"]
    processed = stats["processed"]
    escalated = stats["escalated"]
    with_interaction = stats.get("with_interaction", 0)
    automated = stats.get("automated", 0)
    llm_used = stats.get("llm_used", 0)
    without_interaction = max(0, total - with_interaction)

    lines = [
        "📊 <b>Статистика Intercom</b>",
        f"📅 {start:%d.%m.%Y} — {end:%d.%m.%Y}",
        "",
        f"🔹 Всего обращений: <b>{total}</b> (100.0%)",
        f"✅ Обработано без эскалации: <b>{processed}</b> ({_pct(processed, total):.1f}%)",
        f"⚠️ Эскалировано: <b>{escalated}</b> ({_pct(escalated, total):.1f}%)",
        f"🧩 Есть взаимодействие: <b>{with_interaction}</b> ({_pct(with_interaction, total):.1f}%)",
        f"⏳ Без взаимодействий: <b>{without_interaction}</b> ({_pct(without_interaction, total):.1f}%)",
        "",
        "<b>Результат pipeline:</b>",
    ]

    results = dict(stats.get("results") or [])
    result_den = processed
    lines += [
        f"• Шаблон: {results.get('template', 0)} ({_pct(results.get('template', 0), result_den):.1f}%)",
        f"• LLM: {results.get('llm', 0)} ({_pct(results.get('llm', 0), result_den):.1f}%)",
        f"• Игнор: {results.get('ignored', 0)} ({_pct(results.get('ignored', 0), result_den):.1f}%)",
    ]

    types = dict(stats.get("request_types") or [])
    if types:
        lines += [
            "",
            "<b>Тип обращений:</b>",
            f"• Диалоги: {types.get('conversation', 0)} ({_pct(types.get('conversation', 0), total):.1f}%)",
            f"• Тикеты: {types.get('ticket', 0)} ({_pct(types.get('ticket', 0), total):.1f}%)",
            f"• Другое: {types.get('other', 0)} ({_pct(types.get('other', 0), total):.1f}%)",
        ]

    if with_interaction:
        lines += [
            "",
            "<b>Автоматизация:</b>",
            f"• Automated: {automated} ({_pct(automated, with_interaction):.1f}%)",
            f"• Использован LLM: {llm_used} ({_pct(llm_used, with_interaction):.1f}%)",
        ]

    reasons = stats.get("reasons") or []
    if reasons:
        labels = {
            "user_requested_operator": "Запросил оператора",
            "no_category": "Нет категории",
            "attachments": "Вложения",
            "llm_cannot_answer": "LLM не смогла ответить",
            "wants_new_school": "Хочет в новую школу",
            "internal_error": "Внутренняя ошибка",
            "llm_noise": "LLM noise",
            "clarification_exhausted": "Исчерпаны уточнения",
            "delivery_failure": "Ошибка доставки",
            "high_risk_refund": "Высокорисковый возврат",
            "high_risk_personal_data": "Персональные данные",
            "high_risk_complaint": "Высокорисковая жалоба",
        }
        lines += ["", "<b>Причины эскалации:</b>"]
        for reason, count in reasons:
            key = getattr(reason, "value", reason)
            lines.append(f"• {labels.get(key, key)}: {count} ({_pct(count, escalated):.1f}%)")

    return "\n".join(lines)
