from app.core.exceptions import (
    BadRequestException,
    ConflictException,
    ForbiddenException,
    NotFoundException,
)
from app.models.ip_block import IPBlockSource, IPBlockStatus
from app.models.user import User, UserRole
from app.repositories.ip_block_repository import IPBlockRepository
from app.schemas.ip_block import (
    IPBlockCreateInDB,
    IPBlockCreateRequest,
    IPBlockListResponse,
    IPBlockResponse,
    IPBlockUpdateInDB,
    IPBlockUpdateRequest,
)


class IPBlockService:
    """Business logic for administrator-managed IP blocks."""

    def __init__(self, repository: IPBlockRepository) -> None:
        self.repository = repository

    def _assert_admin(self, actor: User) -> None:
        """Retain service-level RBAC as defense in depth."""
        if actor.role != UserRole.ADMIN.value:
            raise ForbiddenException(
                error_code="IP_BLOCK_FORBIDDEN",
                message="You are not allowed to manage IP blocks.",
            )

    async def _assert_no_active_duplicate(
        self,
        ip_address: str,
        status: str,
        exclude_id: int | None = None,
    ) -> None:
        if status != IPBlockStatus.ACTIVE.value:
            return
        existing = await self.repository.get_active_by_ip(ip_address, exclude_id=exclude_id)
        if existing is not None:
            raise ConflictException(
                error_code="IP_BLOCK_ALREADY_ACTIVE",
                message="This IP address already has an active block.",
            )

    async def create_block(
        self,
        actor: User,
        payload: IPBlockCreateRequest,
    ) -> IPBlockResponse:
        """Create an administrator-authored exact-address block."""
        self._assert_admin(actor)
        await self._assert_no_active_duplicate(payload.ip_address, payload.status.value)
        block = await self.repository.create_block(
            IPBlockCreateInDB(
                ip_address=payload.ip_address,
                reason=payload.reason,
                source=IPBlockSource.MANUAL.value,
                status=payload.status.value,
                created_by=actor.id,
            )
        )
        return IPBlockResponse.model_validate(block)

    async def list_blocks(
        self,
        actor: User,
        skip: int,
        limit: int,
        status: str | None,
    ) -> IPBlockListResponse:
        """List administrator-visible IP blocks."""
        self._assert_admin(actor)
        blocks = await self.repository.list_blocks(skip=skip, limit=limit, status=status)
        return IPBlockListResponse(
            items=[IPBlockResponse.model_validate(block) for block in blocks],
            skip=skip,
            limit=limit,
            total=await self.repository.count_blocks(status),
        )

    async def get_block(self, actor: User, block_id: int) -> IPBlockResponse:
        """Return one IP block."""
        self._assert_admin(actor)
        block = await self.repository.get_by_id(block_id)
        if block is None:
            raise NotFoundException(
                error_code="IP_BLOCK_NOT_FOUND",
                message="IP block not found.",
            )
        return IPBlockResponse.model_validate(block)

    async def update_block(
        self,
        actor: User,
        block_id: int,
        payload: IPBlockUpdateRequest,
    ) -> IPBlockResponse:
        """Update reason or lifecycle status."""
        self._assert_admin(actor)
        if payload.model_dump(exclude_unset=True) == {}:
            raise BadRequestException(
                error_code="IP_BLOCK_INVALID_UPDATE",
                message="At least one updatable field is required.",
            )
        block = await self.repository.get_by_id(block_id)
        if block is None:
            raise NotFoundException(
                error_code="IP_BLOCK_NOT_FOUND",
                message="IP block not found.",
            )
        target_status = payload.status.value if payload.status is not None else block.status
        await self._assert_no_active_duplicate(
            block.ip_address,
            target_status,
            exclude_id=block.id,
        )
        update_data = payload.model_dump(exclude_unset=True)
        if payload.status is not None:
            update_data["status"] = payload.status.value
        updated = await self.repository.update_block(block, IPBlockUpdateInDB(**update_data))
        return IPBlockResponse.model_validate(updated)

    async def disable_block(self, actor: User, block_id: int) -> None:
        """Soft-delete an IP block."""
        self._assert_admin(actor)
        block = await self.repository.get_by_id(block_id)
        if block is None:
            raise NotFoundException(
                error_code="IP_BLOCK_NOT_FOUND",
                message="IP block not found.",
            )
        if block.status != IPBlockStatus.DISABLED.value:
            await self.repository.update_block(
                block,
                IPBlockUpdateInDB(status=IPBlockStatus.DISABLED.value),
            )
