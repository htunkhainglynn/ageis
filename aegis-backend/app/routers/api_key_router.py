from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import require_api_key_manager
from app.core.database import get_db
from app.models.user import User
from app.repositories.api_key_repository import APIKeyRepository
from app.repositories.user_repository import UserRepository
from app.schemas.api_key import (
    APIKeyCreatedResponse,
    APIKeyCreateRequest,
    APIKeyListResponse,
    APIKeyMetadataResponse,
    APIKeyUpdateRequest,
)
from app.schemas.base import ApiResponse, success_response
from app.services.api_key_service import APIKeyService

router = APIRouter(prefix="/api-keys", tags=["API Keys"])


def get_api_key_service(db: AsyncSession = Depends(get_db)) -> APIKeyService:
    """Provide a request-scoped API key service instance."""
    api_key_repository = APIKeyRepository(db=db)
    user_repository = UserRepository(db=db)
    return APIKeyService(api_key_repository=api_key_repository, user_repository=user_repository)


@router.post(
    "",
    response_model=ApiResponse[APIKeyCreatedResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create API key",
    description="Generate a new API key and return raw key only once.",
)
async def create_api_key(
    payload: APIKeyCreateRequest,
    actor: User = Depends(require_api_key_manager),
    api_key_service: APIKeyService = Depends(get_api_key_service),
) -> ApiResponse[APIKeyCreatedResponse]:
    """Create API key.

    Generate and securely persist a new API key for the authenticated user.
    """
    created_api_key = await api_key_service.create_api_key(
        actor_subject=str(actor.id),
        payload=payload,
    )
    return success_response(message="API key created successfully.", data=created_api_key)


@router.get(
    "",
    response_model=ApiResponse[APIKeyListResponse],
    summary="List API keys",
    description="List API key metadata for the authenticated user.",
)
async def list_api_keys(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=10, ge=1, le=100),
    actor: User = Depends(require_api_key_manager),
    api_key_service: APIKeyService = Depends(get_api_key_service),
) -> ApiResponse[APIKeyListResponse]:
    """List API keys.

    Return paginated API key metadata for the authenticated user.
    """
    api_keys = await api_key_service.list_api_keys(
        actor_subject=str(actor.id),
        skip=skip,
        limit=limit,
    )
    return success_response(message="API keys fetched successfully.", data=api_keys)


@router.get(
    "/{api_key_id}",
    response_model=ApiResponse[APIKeyMetadataResponse],
    summary="Get API key",
    description="Retrieve API key metadata by identifier.",
)
async def get_api_key(
    api_key_id: int,
    actor: User = Depends(require_api_key_manager),
    api_key_service: APIKeyService = Depends(get_api_key_service),
) -> ApiResponse[APIKeyMetadataResponse]:
    """Get API key.

    Return API key metadata for a single API key record.
    """
    api_key = await api_key_service.get_api_key(
        actor_subject=str(actor.id),
        api_key_id=api_key_id,
    )
    return success_response(message="API key fetched successfully.", data=api_key)


@router.patch(
    "/{api_key_id}",
    response_model=ApiResponse[APIKeyMetadataResponse],
    summary="Update API key",
    description="Update API key name and scopes.",
)
async def update_api_key(
    api_key_id: int,
    payload: APIKeyUpdateRequest,
    actor: User = Depends(require_api_key_manager),
    api_key_service: APIKeyService = Depends(get_api_key_service),
) -> ApiResponse[APIKeyMetadataResponse]:
    """Update API key.

    Update mutable metadata fields for an API key.
    """
    updated_api_key = await api_key_service.update_api_key(
        actor_subject=str(actor.id),
        api_key_id=api_key_id,
        payload=payload,
    )
    return success_response(message="API key updated successfully.", data=updated_api_key)


@router.delete(
    "/{api_key_id}",
    response_model=ApiResponse[None],
    status_code=status.HTTP_200_OK,
    summary="Revoke API key",
    description="Soft-revoke an API key for the authenticated owner or admin.",
)
async def revoke_api_key(
    api_key_id: int,
    actor: User = Depends(require_api_key_manager),
    api_key_service: APIKeyService = Depends(get_api_key_service),
) -> ApiResponse[None]:
    """Revoke API key.

    Soft-revoke API key by changing its status to revoked.
    """
    await api_key_service.revoke_api_key(
        actor_subject=str(actor.id),
        api_key_id=api_key_id,
    )
    return success_response(message="API key revoked successfully.", data=None)
