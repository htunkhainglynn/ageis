from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rate_limit_rule import RateLimitRule, RateLimitRuleStatus
from app.repositories.base import BaseRepository
from app.schemas.rate_limit_rule import RateLimitRuleCreateInDB, RateLimitRuleUpdateInDB


class RateLimitRuleRepository(
    BaseRepository[RateLimitRule, RateLimitRuleCreateInDB, RateLimitRuleUpdateInDB]
):
    """Repository for rate limit rule persistence operations."""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(RateLimitRule, db)

    async def create_rule(self, payload: RateLimitRuleCreateInDB) -> RateLimitRule:
        """Create a new rate limit rule record."""
        rule = RateLimitRule(**payload.model_dump())
        self.db.add(rule)
        await self.db.commit()
        await self.db.refresh(rule)
        return rule

    async def update_rule(self, rule: RateLimitRule, payload: RateLimitRuleUpdateInDB) -> RateLimitRule:
        """Update mutable fields on an existing rule."""
        update_data = payload.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(rule, key, value)

        await self.db.commit()
        await self.db.refresh(rule)
        return rule

    async def list_rules(
        self,
        skip: int,
        limit: int,
        scope_type: str | None,
        status: str | None,
    ) -> list[RateLimitRule]:
        """List rules with optional filtering and pagination."""
        query = select(RateLimitRule)

        if scope_type is not None:
            query = query.where(RateLimitRule.scope_type == scope_type)
        if status is not None:
            query = query.where(RateLimitRule.status == status)

        query = query.order_by(RateLimitRule.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def count_rules(self, scope_type: str | None, status: str | None) -> int:
        """Count rules with optional filtering."""
        query = select(func.count(RateLimitRule.id))

        if scope_type is not None:
            query = query.where(RateLimitRule.scope_type == scope_type)
        if status is not None:
            query = query.where(RateLimitRule.status == status)

        result = await self.db.execute(query)
        return int(result.scalar_one())

    async def get_active_rule_by_scope(
        self,
        scope_type: str,
        scope_value: str | None,
        exclude_id: int | None = None,
    ) -> RateLimitRule | None:
        """Return active rule that matches the same scope tuple."""
        scope_value_clause = (
            RateLimitRule.scope_value.is_(None)
            if scope_value is None
            else RateLimitRule.scope_value == scope_value
        )

        query = select(RateLimitRule).where(
            and_(
                RateLimitRule.scope_type == scope_type,
                scope_value_clause,
                RateLimitRule.status == "active",
            )
        )

        if exclude_id is not None:
            query = query.where(RateLimitRule.id != exclude_id)

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_active_rules(self) -> list[RateLimitRule]:
        """Return all active rules for reverse-proxy policy enforcement."""
        result = await self.db.execute(
            select(RateLimitRule)
            .where(RateLimitRule.status == RateLimitRuleStatus.ACTIVE.value)
            .order_by(RateLimitRule.id.asc())
        )
        return list(result.scalars().all())
