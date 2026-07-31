from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ip_block import IPBlock, IPBlockStatus
from app.repositories.base import BaseRepository
from app.schemas.ip_block import IPBlockCreateInDB, IPBlockUpdateInDB


class IPBlockRepository(BaseRepository[IPBlock, IPBlockCreateInDB, IPBlockUpdateInDB]):
    """Persistence operations for IP blocks."""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(IPBlock, db)

    async def create_block(self, payload: IPBlockCreateInDB) -> IPBlock:
        """Persist a new IP block."""
        block = IPBlock(**payload.model_dump())
        self.db.add(block)
        await self.db.commit()
        await self.db.refresh(block)
        return block

    async def update_block(self, block: IPBlock, payload: IPBlockUpdateInDB) -> IPBlock:
        """Update mutable fields on an IP block."""
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(block, key, value)
        await self.db.commit()
        await self.db.refresh(block)
        return block

    async def list_blocks(
        self,
        skip: int,
        limit: int,
        status: str | None,
    ) -> list[IPBlock]:
        """List IP blocks with optional status filtering."""
        query = select(IPBlock)
        if status is not None:
            query = query.where(IPBlock.status == status)
        result = await self.db.execute(
            query.order_by(IPBlock.created_at.desc()).offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def count_blocks(self, status: str | None) -> int:
        """Count IP blocks with optional status filtering."""
        query = select(func.count(IPBlock.id))
        if status is not None:
            query = query.where(IPBlock.status == status)
        result = await self.db.execute(query)
        return int(result.scalar_one())

    async def get_active_by_ip(
        self,
        ip_address: str,
        exclude_id: int | None = None,
    ) -> IPBlock | None:
        """Return an active block matching one canonical address."""
        query = select(IPBlock).where(
            IPBlock.ip_address == ip_address,
            IPBlock.status == IPBlockStatus.ACTIVE.value,
        )
        if exclude_id is not None:
            query = query.where(IPBlock.id != exclude_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_active_blocks(self) -> list[IPBlock]:
        """Return active blocks for proxy policy distribution."""
        result = await self.db.execute(
            select(IPBlock)
            .where(IPBlock.status == IPBlockStatus.ACTIVE.value)
            .order_by(IPBlock.id.asc())
        )
        return list(result.scalars().all())
