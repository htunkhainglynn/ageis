from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import require_admin
from app.core.database import get_db
from app.models.ip_block import IPBlockStatus
from app.models.user import User
from app.repositories.ip_block_repository import IPBlockRepository
from app.schemas.base import ApiResponse, success_response
from app.schemas.ip_block import (
    IPBlockCreateRequest,
    IPBlockListResponse,
    IPBlockResponse,
    IPBlockUpdateRequest,
)
from app.services.ip_block_service import IPBlockService

router = APIRouter(prefix="/ip-blocks", tags=["IP Blocks"])


def get_ip_block_service(db: AsyncSession = Depends(get_db)) -> IPBlockService:
    """Provide a request-scoped IP block service."""
    return IPBlockService(IPBlockRepository(db=db))


@router.post(
    "",
    response_model=ApiResponse[IPBlockResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create manual IP block",
)
async def create_ip_block(
    payload: IPBlockCreateRequest,
    actor: User = Depends(require_admin),
    service: IPBlockService = Depends(get_ip_block_service),
) -> ApiResponse[IPBlockResponse]:
    """Block an exact IPv4 or IPv6 address. Admin only."""
    block = await service.create_block(actor=actor, payload=payload)
    return success_response(message="IP address blocked successfully.", data=block)


@router.get(
    "",
    response_model=ApiResponse[IPBlockListResponse],
    summary="List IP blocks",
)
async def list_ip_blocks(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=10, ge=1, le=100),
    status_filter: IPBlockStatus | None = Query(default=None, alias="status"),
    actor: User = Depends(require_admin),
    service: IPBlockService = Depends(get_ip_block_service),
) -> ApiResponse[IPBlockListResponse]:
    """List IP blocks. Admin only."""
    blocks = await service.list_blocks(
        actor=actor,
        skip=skip,
        limit=limit,
        status=status_filter.value if status_filter is not None else None,
    )
    return success_response(message="IP blocks fetched successfully.", data=blocks)


@router.get(
    "/{block_id}",
    response_model=ApiResponse[IPBlockResponse],
    summary="Get IP block",
)
async def get_ip_block(
    block_id: int,
    actor: User = Depends(require_admin),
    service: IPBlockService = Depends(get_ip_block_service),
) -> ApiResponse[IPBlockResponse]:
    """Get one IP block. Admin only."""
    block = await service.get_block(actor=actor, block_id=block_id)
    return success_response(message="IP block fetched successfully.", data=block)


@router.patch(
    "/{block_id}",
    response_model=ApiResponse[IPBlockResponse],
    summary="Update IP block",
)
async def update_ip_block(
    block_id: int,
    payload: IPBlockUpdateRequest,
    actor: User = Depends(require_admin),
    service: IPBlockService = Depends(get_ip_block_service),
) -> ApiResponse[IPBlockResponse]:
    """Update an IP block. Admin only."""
    block = await service.update_block(actor=actor, block_id=block_id, payload=payload)
    return success_response(message="IP block updated successfully.", data=block)


@router.delete(
    "/{block_id}",
    response_model=ApiResponse[None],
    summary="Disable IP block",
)
async def disable_ip_block(
    block_id: int,
    actor: User = Depends(require_admin),
    service: IPBlockService = Depends(get_ip_block_service),
) -> ApiResponse[None]:
    """Soft-delete an IP block. Admin only."""
    await service.disable_block(actor=actor, block_id=block_id)
    return success_response(message="IP block disabled successfully.", data=None)
