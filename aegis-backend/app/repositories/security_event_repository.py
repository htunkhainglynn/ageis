from datetime import datetime

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.security_event import SecurityEvent
from app.repositories.base import BaseRepository
from app.schemas.analytics import SecurityEventCreateRequest


class SecurityEventRepository(
    BaseRepository[SecurityEvent, SecurityEventCreateRequest, SecurityEventCreateRequest]
):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(SecurityEvent, db)

    async def create_event(self, payload: SecurityEventCreateRequest) -> SecurityEvent:
        event = SecurityEvent(**payload.model_dump())
        self.db.add(event)
        await self.db.commit()
        await self.db.refresh(event)
        return event

    async def list_events(self, since: datetime, skip: int, limit: int) -> list[SecurityEvent]:
        result = await self.db.execute(
            select(SecurityEvent).where(SecurityEvent.created_at >= since)
            .order_by(SecurityEvent.created_at.desc()).offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def count_events(self, since: datetime) -> int:
        return int((await self.db.execute(
            select(func.count(SecurityEvent.id)).where(SecurityEvent.created_at >= since)
        )).scalar_one())

    async def summary(self, since: datetime) -> tuple[dict[str, int], dict[str, int]]:
        by_type_rows = (await self.db.execute(
            select(SecurityEvent.event_type, func.count(SecurityEvent.id))
            .where(SecurityEvent.created_at >= since).group_by(SecurityEvent.event_type)
        )).all()
        totals = (await self.db.execute(select(
            func.count(SecurityEvent.id),
            func.sum(case((SecurityEvent.event_type == "request_forwarded", 1), else_=0)),
            func.sum(case((SecurityEvent.status_code.between(400, 499), 1), else_=0)),
            func.sum(case((SecurityEvent.event_type == "rate_limited", 1), else_=0)),
            func.sum(case((SecurityEvent.status_code >= 500, 1), else_=0)),
        ).where(SecurityEvent.created_at >= since))).one()
        return (
            {str(name): int(count) for name, count in by_type_rows},
            {
                "total": int(totals[0] or 0), "forwarded": int(totals[1] or 0),
                "blocked": int(totals[2] or 0), "limited": int(totals[3] or 0),
                "errors": int(totals[4] or 0),
            },
        )

    async def count_violations(self, source_ip: str, since: datetime) -> int:
        """Count block-worthy violations from one direct source address."""
        result = await self.db.execute(
            select(func.count(SecurityEvent.id)).where(
                SecurityEvent.source_ip == source_ip,
                SecurityEvent.created_at >= since,
                SecurityEvent.event_type.in_(("threat_detected", "rate_limited")),
            )
        )
        return int(result.scalar_one())
