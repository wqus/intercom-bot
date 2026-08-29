from datetime import datetime

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.requests import EscalatedConversation, InboundEvent, SupportInteraction


INBOUND_TOPICS = (
    "conversation.user.created",
    "conversation.user.replied",
    "ticket.created",
    "ticket.contact.replied",
)

# A final event can have several interaction traces because compound questions
# are split into subquestions. The analytics layer must therefore classify each
# inbound event once, using deterministic outcome precedence.
ANSWER_DECISIONS = (
    "answer_template",
    "answer_llm",
    "choice",
    "clarify",
    "rephrase",
)
FINAL_ANSWER_DECISIONS = (
    "answer_template",
    "answer_llm",
    "choice",
)


class StatisticsRepository:
    """Read-only event-level analytics over the main Intercom application's tables.

    One inbound Intercom webhook event is the reporting unit. Raw interaction
    traces can be multiple rows per event, so all result metrics are aggregated
    back to distinct ``InboundEvent.id`` values.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    def _inbound_scope(self, start: datetime, end: datetime):
        return (
            InboundEvent.created_at >= start,
            InboundEvent.created_at < end,
            InboundEvent.topic.in_(INBOUND_TOPICS),
        )

    def _event_outcomes(self, start: datetime, end: datetime):
        interactions = (
            select(
                SupportInteraction.event_id.label("event_id"),
                func.bool_or(SupportInteraction.decision == "escalate").label("interaction_escalated"),
                func.bool_or(SupportInteraction.decision == "answer_template").label("template"),
                func.bool_or(SupportInteraction.decision == "answer_llm").label("llm"),
                func.bool_or(SupportInteraction.decision == "choice").label("top3"),
                func.bool_or(SupportInteraction.decision == "clarify").label("clarify"),
                func.bool_or(SupportInteraction.decision == "rephrase").label("rephrase"),
                func.bool_or(SupportInteraction.decision == "ignore").label("ignored"),
                func.bool_or(SupportInteraction.escalation_reason == "wants_new_school").label("wants_new_school"),
                func.bool_or(SupportInteraction.automated.is_(True)).label("automated"),
                func.bool_or(SupportInteraction.llm_used.is_(True)).label("llm_used"),
            )
            .where(SupportInteraction.event_id.is_not(None))
            .group_by(SupportInteraction.event_id)
        ).subquery()

        escalations = (
            select(
                EscalatedConversation.source_event_id.label("event_id"),
                func.max(1).label("escalated"),
                func.bool_or(EscalatedConversation.reason == "wants_new_school").label("wants_new_school"),
            )
            .where(EscalatedConversation.source_event_id.is_not(None))
            .group_by(EscalatedConversation.source_event_id)
        ).subquery()

        return (
            select(
                InboundEvent.id.label("event_id"),
                func.coalesce(interactions.c.interaction_escalated, False).label("interaction_escalated"),
                func.coalesce(escalations.c.escalated, 0).label("persistent_escalated"),
                (
                    func.coalesce(interactions.c.wants_new_school, False)
                    | func.coalesce(escalations.c.wants_new_school, False)
                ).label("wants_new_school"),
                func.coalesce(interactions.c.template, False).label("template"),
                func.coalesce(interactions.c.llm, False).label("llm"),
                func.coalesce(interactions.c.top3, False).label("top3"),
                func.coalesce(interactions.c.clarify, False).label("clarify"),
                func.coalesce(interactions.c.rephrase, False).label("rephrase"),
                func.coalesce(interactions.c.ignored, False).label("ignored"),
                func.coalesce(interactions.c.automated, False).label("automated"),
                func.coalesce(interactions.c.llm_used, False).label("llm_used"),
            )
            .select_from(InboundEvent)
            .outerjoin(interactions, interactions.c.event_id == InboundEvent.id)
            .outerjoin(escalations, escalations.c.event_id == InboundEvent.id)
            .where(*self._inbound_scope(start, end))
        ).subquery()

    async def get_total_requests(self, start: datetime, end: datetime) -> int:
        stmt = select(func.count(InboundEvent.id)).where(*self._inbound_scope(start, end))
        return int(await self.session.scalar(stmt) or 0)

    async def get_result_counts(self, start: datetime, end: datetime) -> dict[str, int]:
        """Aggregate one mutually-prioritized outcome per inbound event.

        Reporting categories follow the business contract:
        escalation has highest priority; then LLM answer; then ignored; all
        other supported non-escalated automated outcomes (including Top-3) are
        grouped into ``template``. ``wants_new_school`` is a handled business
        flow and is included in ``processed`` even when it also escalates.
        """
        events = self._event_outcomes(start, end)

        is_escalated = events.c.interaction_escalated | (events.c.persistent_escalated == 1)
        is_llm = ~is_escalated & events.c.llm
        is_ignored = ~is_escalated & ~is_llm & events.c.ignored
        is_template = (
            ~is_escalated
            & ~is_llm
            & ~is_ignored
            & (
                events.c.template
                | events.c.top3
                | events.c.clarify
                | events.c.rephrase
                | events.c.wants_new_school
            )
        )

        # A request is considered processed when the system produced any
        # non-escalation outcome. ``wants_new_school`` remains a handled flow
        # even if a separate escalation record exists for the same event.
        processed_system = is_llm | is_ignored | is_template | events.c.wants_new_school

        stmt = select(
            func.count().label("total_scoped"),
            func.sum(case((is_escalated, 1), else_=0)).label("escalated"),
            func.sum(case((processed_system, 1), else_=0)).label("processed"),
            func.sum(case((is_ignored, 1), else_=0)).label("ignored"),
            func.sum(case((is_template, 1), else_=0)).label("template"),
            func.sum(case((is_llm, 1), else_=0)).label("llm"),
            func.sum(case((events.c.automated, 1), else_=0)).label("automated"),
            func.sum(case((events.c.llm_used, 1), else_=0)).label("llm_used"),
        ).select_from(events)

        row = (await self.session.execute(stmt)).one()
        (
            _total_scoped,
            escalated,
            processed,
            ignored,
            template,
            llm,
            automated,
            llm_used,
        ) = [int(value or 0) for value in row]

        total = await self.get_total_requests(start, end)

        with_interaction_stmt = select(
            func.count(func.distinct(SupportInteraction.event_id))
        ).select_from(InboundEvent).join(
            SupportInteraction, SupportInteraction.event_id == InboundEvent.id
        ).where(*self._inbound_scope(start, end))
        with_interaction = int(await self.session.scalar(with_interaction_stmt) or 0)

        return {
            "total": total,
            "escalated": escalated,
            "processed": processed,
            "ignored": ignored,
            "template": template,
            "llm": llm,
            "automated": automated,
            "llm_used": llm_used,
            "with_interaction": with_interaction,
        }

    async def get_escalated_events(self, start: datetime, end: datetime) -> int:
        return (await self.get_result_counts(start, end))["escalated"]

    async def get_escalation_reasons(self, start: datetime, end: datetime):
        """Count one primary escalation reason per escalated inbound event.

        Escalation is normally persisted in ``escalated_conversations`` and also
        represented by an ``escalate`` interaction. We coalesce those two sources
        at event level so the report does not double-count and still sees an
        escalation if one persistence path is missing.
        """
        interaction_reasons = (
            select(
                SupportInteraction.event_id.label("event_id"),
                func.min(SupportInteraction.escalation_reason).label("reason"),
            )
            .where(
                SupportInteraction.event_id.is_not(None),
                SupportInteraction.decision == "escalate",
            )
            .group_by(SupportInteraction.event_id)
        ).subquery()

        persistent_reasons = (
            select(
                EscalatedConversation.source_event_id.label("event_id"),
                func.min(EscalatedConversation.reason).label("reason"),
            )
            .where(EscalatedConversation.source_event_id.is_not(None))
            .group_by(EscalatedConversation.source_event_id)
        ).subquery()

        raw_reason = func.coalesce(
            persistent_reasons.c.reason,
            interaction_reasons.c.reason,
            "no_category",
        )
        # Public reporting intentionally has no ``other`` bucket.
        #
        # - ``wants_new_school`` is not a public escalation reason, but if it
        #   reaches the escalation-reason stream it is grouped into the
        #   existing no-category bucket.
        # - High-risk paths are also intentionally grouped into no-category
        #   for the current reporting contract.
        # - Any future/unknown escalation reason is retained in the aggregate
        #   rather than silently disappearing from the report and is grouped
        #   into no-category until a dedicated public bucket is introduced.
        public_reason = case(
            (raw_reason.in_((
                "wants_new_school",
                "high_risk_refund",
                "high_risk_personal_data",
                "high_risk_complaint",
                "clarification_exhausted",
            )), "no_category"),
            (raw_reason.in_((
                "user_requested_operator",
                "no_category",
                "attachments",
                "llm_cannot_answer",
                "internal_error",
                "delivery_failure",
            )), raw_reason),
            else_="no_category",
        )

        event_reasons = (
            select(
                InboundEvent.id.label("event_id"),
                public_reason.label("reason"),
            )
            .select_from(InboundEvent)
            .outerjoin(
                persistent_reasons,
                persistent_reasons.c.event_id == InboundEvent.id,
            )
            .outerjoin(
                interaction_reasons,
                interaction_reasons.c.event_id == InboundEvent.id,
            )
            .where(*self._inbound_scope(start, end))
            .where(
                (persistent_reasons.c.event_id.is_not(None))
                | (interaction_reasons.c.event_id.is_not(None))
            )
        ).subquery()

        stmt = (
            select(
                event_reasons.c.reason,
                func.count(event_reasons.c.event_id),
            )
            .group_by(event_reasons.c.reason)
            .order_by(func.count(event_reasons.c.event_id).desc())
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
