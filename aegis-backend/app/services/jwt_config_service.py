from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings
from app.core.exceptions import (
    BadRequestException,
    ForbiddenException,
    NotFoundException,
    UnauthorizedException,
)
from app.models.jwt_config import JWTConfig, JWTConfigStatus
from app.models.user import User
from app.repositories.jwt_config_repository import JWTConfigRepository
from app.repositories.user_repository import UserRepository
from app.schemas.jwt_config import (
    JWTConfigCreateInDB,
    JWTConfigCreateRequest,
    JWTConfigListResponse,
    JWTConfigResponse,
    JWTConfigUpdateInDB,
    JWTConfigUpdateRequest,
)


class JWTConfigService:
    """Business logic for JWT validation configuration management."""

    def __init__(
        self,
        jwt_config_repository: JWTConfigRepository,
        user_repository: UserRepository,
    ) -> None:
        self.jwt_config_repository = jwt_config_repository
        self.user_repository = user_repository

    async def _get_actor_user(self, actor_subject: str) -> User:
        """Resolve authenticated actor from token subject."""
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

    def _assert_admin_user(self, actor_user: User) -> None:
        """Ensure the actor has admin privileges for JWT config operations."""
        if not self._is_admin_user(actor_user):
            raise ForbiddenException(
                error_code="JWT_CONFIG_FORBIDDEN",
                message="You are not allowed to manage JWT configurations.",
            )

    def _build_fernet(self) -> Fernet:
        """Build Fernet cipher from environment-backed key material."""
        encryption_key = settings.JWT_CONFIG_ENCRYPTION_KEY.strip()
        if encryption_key == "":
            raise BadRequestException(
                error_code="JWT_CONFIG_ENCRYPTION_KEY_MISSING",
                message="JWT config encryption key is not configured.",
            )

        try:
            return Fernet(encryption_key.encode())
        except ValueError as exc:
            raise BadRequestException(
                error_code="JWT_CONFIG_ENCRYPTION_KEY_INVALID",
                message="JWT config encryption key is invalid.",
            ) from exc

    def _encrypt_signing_key(self, signing_key: str) -> str:
        """Encrypt a signing key before database persistence."""
        return self._build_fernet().encrypt(signing_key.encode()).decode()

    def _decrypt_signing_key(self, encrypted_signing_key: str) -> str:
        """Decrypt persisted signing key for masked display."""
        try:
            return self._build_fernet().decrypt(encrypted_signing_key.encode()).decode()
        except InvalidToken as exc:
            raise BadRequestException(
                error_code="JWT_CONFIG_SIGNING_KEY_DECRYPT_FAILED",
                message="Unable to decrypt stored signing key.",
            ) from exc

    @staticmethod
    def _mask_secret(raw_value: str) -> str:
        """Mask secret values to prevent key material leakage in API responses."""
        if raw_value == "":
            return "****"
        return f"****{raw_value[-4:]}"

    def _validate_ttl_pair(
        self,
        access_token_ttl_seconds: int,
        refresh_token_ttl_seconds: int,
    ) -> None:
        """Ensure access token TTL is shorter than refresh token TTL."""
        if access_token_ttl_seconds >= refresh_token_ttl_seconds:
            raise BadRequestException(
                error_code="JWT_CONFIG_INVALID_TTL",
                message="access_token_ttl_seconds must be shorter than refresh_token_ttl_seconds.",
            )

    def _to_response(self, jwt_config: JWTConfig) -> JWTConfigResponse:
        """Build masked API response model from persisted config."""
        raw_signing_key = self._decrypt_signing_key(jwt_config.signing_key)
        public_key_masked = self._mask_secret(jwt_config.public_key) if jwt_config.public_key is not None else None

        return JWTConfigResponse(
            id=jwt_config.id,
            name=jwt_config.name,
            algorithm=jwt_config.algorithm,
            signing_key_masked=self._mask_secret(raw_signing_key),
            public_key_masked=public_key_masked,
            issuer=jwt_config.issuer,
            audience=jwt_config.audience,
            access_token_ttl_seconds=jwt_config.access_token_ttl_seconds,
            refresh_token_ttl_seconds=jwt_config.refresh_token_ttl_seconds,
            status=jwt_config.status,
            created_by=jwt_config.created_by,
            created_at=jwt_config.created_at,
            updated_at=jwt_config.updated_at,
        )

    async def create_config(
        self,
        actor_subject: str,
        payload: JWTConfigCreateRequest,
    ) -> JWTConfigResponse:
        """Create a new JWT config in disabled state."""
        actor_user = await self._get_actor_user(actor_subject)
        self._assert_admin_user(actor_user)

        jwt_config_input = JWTConfigCreateInDB(
            name=payload.name,
            algorithm=payload.algorithm.value,
            signing_key=self._encrypt_signing_key(payload.signing_key),
            public_key=payload.public_key,
            issuer=payload.issuer,
            audience=payload.audience,
            access_token_ttl_seconds=payload.access_token_ttl_seconds,
            refresh_token_ttl_seconds=payload.refresh_token_ttl_seconds,
            status=JWTConfigStatus.DISABLED.value,
            created_by=actor_user.id,
        )

        created_config = await self.jwt_config_repository.create_config(jwt_config_input)
        return self._to_response(created_config)

    async def list_configs(self, actor_subject: str, skip: int, limit: int) -> JWTConfigListResponse:
        """List JWT configs with pagination for admin users."""
        actor_user = await self._get_actor_user(actor_subject)
        self._assert_admin_user(actor_user)

        configs = await self.jwt_config_repository.list_configs(skip=skip, limit=limit)
        total = await self.jwt_config_repository.count_configs()

        return JWTConfigListResponse(
            items=[self._to_response(jwt_config) for jwt_config in configs],
            skip=skip,
            limit=limit,
            total=total,
        )

    async def get_config(self, actor_subject: str, config_id: int) -> JWTConfigResponse:
        """Retrieve one JWT config by id for admin users."""
        actor_user = await self._get_actor_user(actor_subject)
        self._assert_admin_user(actor_user)

        jwt_config = await self.jwt_config_repository.get_by_id(config_id)
        if jwt_config is None:
            raise NotFoundException(
                error_code="JWT_CONFIG_NOT_FOUND",
                message="JWT config not found.",
            )

        return self._to_response(jwt_config)

    async def update_config(
        self,
        actor_subject: str,
        config_id: int,
        payload: JWTConfigUpdateRequest,
    ) -> JWTConfigResponse:
        """Update non-key JWT config fields."""
        actor_user = await self._get_actor_user(actor_subject)
        self._assert_admin_user(actor_user)

        if payload.model_dump(exclude_unset=True) == {}:
            raise BadRequestException(
                error_code="JWT_CONFIG_INVALID_UPDATE",
                message="At least one updatable field is required.",
            )

        existing_config = await self.jwt_config_repository.get_by_id(config_id)
        if existing_config is None:
            raise NotFoundException(
                error_code="JWT_CONFIG_NOT_FOUND",
                message="JWT config not found.",
            )

        target_access_ttl = (
            payload.access_token_ttl_seconds
            if payload.access_token_ttl_seconds is not None
            else existing_config.access_token_ttl_seconds
        )
        target_refresh_ttl = (
            payload.refresh_token_ttl_seconds
            if payload.refresh_token_ttl_seconds is not None
            else existing_config.refresh_token_ttl_seconds
        )
        self._validate_ttl_pair(
            access_token_ttl_seconds=target_access_ttl,
            refresh_token_ttl_seconds=target_refresh_ttl,
        )

        update_payload = JWTConfigUpdateInDB(**payload.model_dump(exclude_unset=True))
        updated_config = await self.jwt_config_repository.update_config(existing_config, update_payload)
        return self._to_response(updated_config)

    async def activate_config(self, actor_subject: str, config_id: int) -> JWTConfigResponse:
        """Activate one config and deactivate previously active config."""
        actor_user = await self._get_actor_user(actor_subject)
        self._assert_admin_user(actor_user)

        existing_config = await self.jwt_config_repository.get_by_id(config_id)
        if existing_config is None:
            raise NotFoundException(
                error_code="JWT_CONFIG_NOT_FOUND",
                message="JWT config not found.",
            )

        if existing_config.status == JWTConfigStatus.ACTIVE.value:
            return self._to_response(existing_config)

        activated_config = await self.jwt_config_repository.activate_config(existing_config)
        return self._to_response(activated_config)

    async def disable_config(self, actor_subject: str, config_id: int) -> None:
        """Soft-delete a non-active JWT config by setting disabled status."""
        actor_user = await self._get_actor_user(actor_subject)
        self._assert_admin_user(actor_user)

        existing_config = await self.jwt_config_repository.get_by_id(config_id)
        if existing_config is None:
            raise NotFoundException(
                error_code="JWT_CONFIG_NOT_FOUND",
                message="JWT config not found.",
            )

        if existing_config.status == JWTConfigStatus.ACTIVE.value:
            raise BadRequestException(
                error_code="JWT_CONFIG_ACTIVE_DELETE_FORBIDDEN",
                message="Active JWT config cannot be disabled.",
            )

        if existing_config.status == JWTConfigStatus.DISABLED.value:
            return

        await self.jwt_config_repository.update_config(
            existing_config,
            JWTConfigUpdateInDB(status=JWTConfigStatus.DISABLED.value),
        )
