import secrets

from app.core.config import settings
from app.core.exceptions import (
    BadRequestException,
    ForbiddenException,
    NotFoundException,
    UnauthorizedException,
)
from app.core.rate_limit import enforce_api_key_creation_rate_limit
from app.core.security import hash_password
from app.models.api_key import APIKey, APIKeyStatus
from app.models.user import User
from app.repositories.api_key_repository import APIKeyRepository
from app.repositories.user_repository import UserRepository
from app.schemas.api_key import (
    APIKeyCreateInDB,
    APIKeyCreatedResponse,
    APIKeyCreateRequest,
    APIKeyListResponse,
    APIKeyMetadataResponse,
    APIKeyUpdateInDB,
    APIKeyUpdateRequest,
)


class APIKeyService:
    """Business logic for API key lifecycle management."""

    def __init__(
        self,
        api_key_repository: APIKeyRepository,
        user_repository: UserRepository,
    ) -> None:
        self.api_key_repository = api_key_repository
        self.user_repository = user_repository

    async def _get_actor_user(self, actor_subject: str) -> User:
        """Resolve current actor from auth subject."""
        try:
            actor_id = int(actor_subject)
        except ValueError as exc:
            raise UnauthorizedException(
                error_code="AUTH_INVALID_SUBJECT",
                message="Invalid authentication subject.",
            ) from exc

        actor_user = await self.user_repository.get_by_id(actor_id)
        if actor_user is None:
            raise UnauthorizedException(
                error_code="AUTH_USER_NOT_FOUND",
                message="Authenticated user not found.",
            )
        return actor_user

    def _is_admin_user(self, actor_user: User) -> bool:
        """Return whether the actor has admin privileges."""
        admin_role_name = settings.api_key.ADMIN_ROLE_NAME.lower()

        role = getattr(actor_user, "role", None)
        if isinstance(role, str) and role.lower() == admin_role_name:
            return True

        is_admin = getattr(actor_user, "is_admin", None)
        if isinstance(is_admin, bool) and is_admin:
            return True

        roles = getattr(actor_user, "roles", None)
        if isinstance(roles, list):
            for current_role in roles:
                if isinstance(current_role, str) and current_role.lower() == admin_role_name:
                    return True

        return False

    def _assert_owner_or_admin(self, actor_user: User, api_key: APIKey) -> None:
        """Ensure the actor is owner or admin before managing a key."""
        if api_key.owner_id != actor_user.id and not self._is_admin_user(actor_user):
            raise ForbiddenException(
                error_code="API_KEY_FORBIDDEN",
                message="You are not allowed to manage this API key.",
            )

    async def create_api_key(
        self,
        actor_subject: str,
        payload: APIKeyCreateRequest,
    ) -> APIKeyCreatedResponse:
        """Create a new API key and return raw key only once."""
        actor_user = await self._get_actor_user(actor_subject)
        await enforce_api_key_creation_rate_limit(actor_user.id)

        raw_key = f"ak_{secrets.token_urlsafe(settings.api_key.TOKEN_BYTES)}"
        key_prefix = raw_key[: settings.api_key.PREFIX_LENGTH]

        api_key_in_db = APIKeyCreateInDB(
            key_hash=hash_password(raw_key),
            key_prefix=key_prefix,
            owner_id=actor_user.id,
            name=payload.name,
            scopes=payload.scopes,
            status=APIKeyStatus.ACTIVE.value,
            expires_at=payload.expires_at,
        )
        created_api_key = await self.api_key_repository.create_api_key(api_key_in_db)

        metadata = APIKeyMetadataResponse.model_validate(created_api_key)
        return APIKeyCreatedResponse(**metadata.model_dump(), api_key=raw_key)

    async def list_api_keys(self, actor_subject: str, skip: int, limit: int) -> APIKeyListResponse:
        """List API keys for the authenticated user."""
        actor_user = await self._get_actor_user(actor_subject)
        api_keys = await self.api_key_repository.get_keys_by_owner(actor_user.id, skip, limit)
        total = await self.api_key_repository.count_keys_by_owner(actor_user.id)

        return APIKeyListResponse(
            items=[APIKeyMetadataResponse.model_validate(api_key) for api_key in api_keys],
            skip=skip,
            limit=limit,
            total=total,
        )

    async def get_api_key(self, actor_subject: str, api_key_id: int) -> APIKeyMetadataResponse:
        """Retrieve a single API key metadata record."""
        actor_user = await self._get_actor_user(actor_subject)
        api_key = await self.api_key_repository.get_by_id(api_key_id)
        if api_key is None:
            raise NotFoundException(
                error_code="API_KEY_NOT_FOUND",
                message="API key not found.",
            )

        self._assert_owner_or_admin(actor_user, api_key)
        return APIKeyMetadataResponse.model_validate(api_key)

    async def update_api_key(
        self,
        actor_subject: str,
        api_key_id: int,
        payload: APIKeyUpdateRequest,
    ) -> APIKeyMetadataResponse:
        """Update API key mutable metadata fields."""
        if payload.name is None and payload.scopes is None:
            raise BadRequestException(
                error_code="API_KEY_INVALID_UPDATE",
                message="At least one updatable field is required.",
            )

        actor_user = await self._get_actor_user(actor_subject)
        api_key = await self.api_key_repository.get_by_id(api_key_id)
        if api_key is None:
            raise NotFoundException(
                error_code="API_KEY_NOT_FOUND",
                message="API key not found.",
            )

        self._assert_owner_or_admin(actor_user, api_key)

        api_key_update = APIKeyUpdateInDB(
            name=payload.name,
            scopes=payload.scopes,
        )
        updated_api_key = await self.api_key_repository.update_api_key(api_key, api_key_update)
        return APIKeyMetadataResponse.model_validate(updated_api_key)

    async def revoke_api_key(self, actor_subject: str, api_key_id: int) -> None:
        """Soft-revoke an API key by changing its status."""
        actor_user = await self._get_actor_user(actor_subject)
        api_key = await self.api_key_repository.get_by_id(api_key_id)
        if api_key is None:
            raise NotFoundException(
                error_code="API_KEY_NOT_FOUND",
                message="API key not found.",
            )

        self._assert_owner_or_admin(actor_user, api_key)
        if api_key.status == APIKeyStatus.REVOKED.value:
            return

        await self.api_key_repository.update_api_key(
            api_key,
            APIKeyUpdateInDB(status=APIKeyStatus.REVOKED.value),
        )
