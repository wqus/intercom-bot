from datetime import datetime

from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.requests import EscalatedConversation, InboundEvent, SupportInteraction


INBOUND_TOPICS = (
    "conversation.user.created",
    "conversation.user.replied",
    "ticket.created",
    "ticket.contact.replied",
)


class StatisticsRepository:
    """Read-only analytics over the main Intercom application's tables.

    The calendar day is defined by ``inbound_events.created_at``. All derived
    metrics are joined back to that inbound event, so an escalation or
    interaction created later cannot move a request into another report day.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    def _inbound_scope(self, start: datetime, end: datetime):
        return (
            InboundEvent.created_at >= start,
            InboundEvent.created_at < end,
            InboundEvent.topic.in_(INBOUND_TOPICS),
        )

    async def get_total_requests(self, start: datetime, end: datetime) -> int:
        stmt = select(func.count(InboundEvent.id)).where(*self._inbound_scope(start, end))
        return int(await self.session.scalar(stmt) or 0)

    async def get_result_counts(self, start: datetime, end: datetime) -> dict[str, int]:
        interactions = (
            select(
                SupportInteraction.event_id.label("event_id"),
                func.bool_or(SupportInteraction.decision == "escalate").label("escalated"),
                func.bool_or(SupportInteraction.decision == "answer_llm").label("llm"),
                func.bool_or(SupportInteraction.decision == "answer_template").label("template"),
                func.bool_or(SupportInteraction.decision == "ignore").label("ignored"),
                func.bool_or(SupportInteraction.automated.is_(True)).label("automated"),
                func.bool_or(SupportInteraction.llm_used.is_(True)).label("llm_used"),
            )
            .where(SupportInteraction.event_id.is_not(None))
            .group_by(SupportInteraction.event_id)
        ).subquery()

        joined = (
            select(
                InboundEvent.id.label("event_id"),
                func.coalesce(interactions.c.escalated, False).label("escalated"),
                func.coalesce(interactions.c.llm, False).label("llm"),
                func.coalesce(interactions.c.template, False).label("template"),
                func.coalesce(interactions.c.ignored, False).label("ignored"),
                func.coalesce(interactions.c.automated, False).label("automated"),
                func.coalesce(interactions.c.llm_used, False).label("llm_used"),
            )
            .select_from(InboundEvent)
            .outerjoin(interactions, interactions.c.event_id == InboundEvent.id)
            .where(*self._inbound_scope(start, end))
        ).subquery()

        stmt = select(
            func.coalesce(func.sum(case((joined.c.escalated, 1), else_=0)), 0),
            func.coalesce(func.sum(case((and_(~joined.c.escalated, joined.c.llm), 1), else_=0)), 0),
            func.coalesce(func.sum(case((and_(~joined.c.escalated, ~joined.c.llm, joined.c.template), 1), else_=0)), 0),
            func.coalesce(func.sum(case((and_(~joined.c.escalated, ~joined.c.llm, ~joined.c.template, joined.c.ignored), 1), else_=0)), 0),
            func.coalesce(func.sum(case((joined.c.automated, 1), else_=0)), 0),
            func.coalesce(func.sum(case((joined.c.llm_used, 1), else_=0)), 0),
        )
        row = (await self.session.execute(stmt)).one()

        # Count interacted events separately: boolean flags may all be false for
        # a valid interaction, so they cannot be used to detect interaction itself.
        with_interaction_stmt = select(func.count(func.distinct(SupportInteraction.event_id))).select_from(
            InboundEvent
        ).join(
            SupportInteraction, SupportInteraction.event_id == InboundEvent.id
        ).where(*self._inbound_scope(start, end))
        with_interaction = int(await self.session.scalar(with_interaction_stmt) or 0)

        return {
            "escalated": int(row[0] or 0),
            "llm": int(row[1] or 0),
            "template": int(row[2] or 0),
            "ignored": int(row[3] or 0),
            "automated": int(row[4] or 0),
            "llm_used": int(row[5] or 0),
            "with_interaction": with_interaction,
        }

    async def get_escalated_events(self, start: datetime, end: datetime) -> int:
        stmt = (
            select(func.count(func.distinct(EscalatedConversation.source_event_id)))
            .select_from(InboundEvent)
            .join(EscalatedConversation, EscalatedConversation.source_event_id == InboundEvent.id)
            .where(*self._inbound_scope(start, end))
        )
        return int(await self.session.scalar(stmt) or 0)

    async def get_escalation_reasons(self, start: datetime, end: datetime):
        stmt = (
            select(
                EscalatedConversation.reason,
                func.count(func.distinct(EscalatedConversation.source_event_id)),
            )
            .select_from(InboundEvent)
            .join(EscalatedConversation, EscalatedConversation.source_event_id == InboundEvent.id)
            .where(*self._inbound_scope(start, end))
            .group_by(EscalatedConversation.reason)
            .order_by(func.count(func.distinct(EscalatedConversation.source_event_id)).desc())
        )
        result = await self.session.execute(stmt)
        return result.all()

    async def get_request_types(self, start: datetime, end: datetime):
        stmt = (
            select(
                case(
                    (InboundEvent.topic.like("conversation.%"), "conversation"),
                    (InboundEvent.topic.like("ticket.%"), "ticket"),
                    else_="other",
                ).label("request_type"),
                func.count(InboundEvent.id),
            )
            .where(*self._inbound_scope(start, end))
            .group_by("request_type")
        )
        result = await self.session.execute(stmt)
        return result.all()

    async def export_requests(self, start: datetime | None = None, end: datetime | None = None):
        conditions = [InboundEvent.topic.in_(INBOUND_TOPICS)]
        if start is not None:
            conditions.append(InboundEvent.created_at >= start)
        if end is not None:
            conditions.append(InboundEvent.created_at < end)

        stmt = select(InboundEvent).where(*conditions).order_by(InboundEvent.created_at)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
