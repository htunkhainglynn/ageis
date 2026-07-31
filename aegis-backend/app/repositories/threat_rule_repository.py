from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.threat_rule import ThreatRule, ThreatRuleStatus
from app.repositories.base import BaseRepository
from app.schemas.threat_rule import ThreatRuleCreateInDB, ThreatRuleUpdateInDB


class ThreatRuleRepository(
    BaseRepository[ThreatRule, ThreatRuleCreateInDB, ThreatRuleUpdateInDB]
):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(ThreatRule, db)

    async def create_rule(self, payload: ThreatRuleCreateInDB) -> ThreatRule:
        rule = ThreatRule(**payload.model_dump())
        self.db.add(rule)
        await self.db.commit()
        await self.db.refresh(rule)
        return rule

    async def update_rule(
        self, rule: ThreatRule, payload: ThreatRuleUpdateInDB
    ) -> ThreatRule:
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(rule, key, value)
        await self.db.commit()
        await self.db.refresh(rule)
        return rule

    async def list_rules(
        self, skip: int, limit: int, status: str | None
    ) -> list[ThreatRule]:
        query = select(ThreatRule)
        if status is not None:
            query = query.where(ThreatRule.status == status)
        result = await self.db.execute(
            query.order_by(ThreatRule.created_at.desc()).offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def count_rules(self, status: str | None) -> int:
        query = select(func.count(ThreatRule.id))
        if status is not None:
            query = query.where(ThreatRule.status == status)
        return int((await self.db.execute(query)).scalar_one())

    async def list_active_rules(self) -> list[ThreatRule]:
        result = await self.db.execute(
            select(ThreatRule)
            .where(ThreatRule.status == ThreatRuleStatus.ACTIVE.value)
            .order_by(ThreatRule.id.asc())
        )
        return list(result.scalars().all())
