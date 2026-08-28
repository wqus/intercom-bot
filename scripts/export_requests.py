"""Export real Intercom requests from the CURRENT production DB.

Usage:
  python scripts/export_requests.py --output requests.csv
  python scripts/export_requests.py --output requests.jsonl --since 2026-08-01
  python scripts/export_requests.py --output requests.csv --until 2026-08-27

The source of truth is inbound_events. The latest customer message is extracted
from the stored Intercom payload using the same semantics as the main parser.
No production records are modified.
"""
from __future__ import annotations
import argparse, asyncio, csv, json, sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.dependencies import get_db
from app.repositories.statistics_repository import StatisticsRepository


def strip_html(value: str) -> str:
    import re
    return re.sub(r"<[^>]+>", "", value or "").strip()


def ts(value):
    if value in (None, ""):
        return -1.0
    try:
        return float(value)
    except (TypeError, ValueError):
        try:
            return datetime.fromisoformat(str(value).replace("Z","+00:00")).timestamp()
        except Exception:
            return -1.0


def extract_message(event) -> tuple[str, str, bool]:
    payload = event.payload or {}
    topic = event.topic
    item = payload.get("data", {}).get("item", {}) or {}

    if topic.startswith("conversation."):
        source = item.get("source", {}) or {}
        parts = item.get("conversation_parts", {}).get("conversation_parts", []) or []
        user_parts = [
            p for p in parts
            if (p.get("author", {}) or {}).get("type") == "user" and p.get("body")
        ]
        if (source.get("author", {}) or {}).get("type") == "user" and source.get("body"):
            user_parts.append(source)
        if not user_parts:
            return "", "", False
        part = max(enumerate(user_parts), key=lambda pair: (ts(pair[1].get("created_at")), pair[0]))[1]
        return strip_html(part.get("body","")), str(part.get("created_at") or item.get("updated_at") or ""), bool(part.get("attachments"))

    if topic == "ticket.contact.replied":
        part = item.get("ticket_part", {}) or {}
        return strip_html(part.get("body","")), str(part.get("created_at") or item.get("updated_at") or ""), bool(part.get("attachments"))

    attrs = item.get("ticket_attributes", {}) or {}
    return strip_html(attrs.get("_default_description_","")), str(item.get("updated_at") or ""), False


async def run(args):
    start = datetime.fromisoformat(args.since).replace(tzinfo=timezone.utc) if args.since else None
    end = datetime.fromisoformat(args.until).replace(tzinfo=timezone.utc) if args.until else None
    async for session in get_db():
        repo = StatisticsRepository(session)
        events = await repo.export_requests(start, end)
        rows = []
        for event in events:
            question, message_at, attachments = extract_message(event)
            if not question:
                continue
            rows.append({
                "event_id": event.id,
                "event_key": event.event_key,
                "provider_event_id": event.provider_event_id,
                "topic": event.topic,
                "entity_id": event.entity_id,
                "created_at": event.created_at.isoformat() if event.created_at else "",
                "message_at": message_at,
                "has_attachments": attachments,
                "question": question,
                "status": event.status,
            })
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        if out.suffix.lower() == ".jsonl":
            out.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
        else:
            with out.open("w", encoding="utf-8-sig", newline="") as fh:
                writer = csv.DictWriter(fh, fieldnames=list(rows[0]) if rows else ["event_id","question"])
                writer.writeheader()
                writer.writerows(rows)
        print(f"exported={len(rows)} -> {out}")
        break


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--since")
    parser.add_argument("--until")
    asyncio.run(run(parser.parse_args()))
