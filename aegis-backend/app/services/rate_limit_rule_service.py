from app.core.config import settings
from app.core.exceptions import (
    BadRequestException,
    ConflictException,
    ForbiddenException,
    NotFoundException,
    UnauthorizedException,
)
from app.models.rate_limit_rule import (
    RateLimitRule,
    RateLimitRuleScopeType,
    RateLimitRuleStatus,
)
from app.models.user import User
from app.repositories.rate_limit_rule_repository import RateLimitRuleRepository
from app.repositories.user_repository import UserRepository
from app.schemas.rate_limit_rule import (
    RateLimitRuleCreateInDB,
    RateLimitRuleCreateRequest,
    RateLimitRuleListResponse,
    RateLimitRuleResponse,
    RateLimitRuleUpdateInDB,
    RateLimitRuleUpdateRequest,
)


class RateLimitRuleService:
    """Business logic for rate limit rule configuration management."""

    def __init__(
        self,
        rate_limit_rule_repository: RateLimitRuleRepository,
        user_repository: UserRepository,
    ) -> None:
        self.rate_limit_rule_repository = rate_limit_rule_repository
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
        """Ensure the actor has admin privileges for write operations."""
        if not self._is_admin_user(actor_user):
            raise ForbiddenException(
                error_code="RATE_LIMIT_RULE_FORBIDDEN",
                message="You are not allowed to manage rate limit rules.",
            )

    def _validate_scope_tuple(self, scope_type: str, scope_value: str | None) -> None:
        """Enforce scope-value consistency constraints."""
        if scope_type == RateLimitRuleScopeType.GLOBAL.value and scope_value is not None:
            raise BadRequestException(
                error_code="RATE_LIMIT_RULE_INVALID_SCOPE",
                message="scope_value must be null for global scope.",
            )

        if scope_type in {
            RateLimitRuleScopeType.API_KEY.value,
            RateLimitRuleScopeType.ROUTE.value,
        } and scope_value is None:
            raise BadRequestException(
                error_code="RATE_LIMIT_RULE_INVALID_SCOPE",
                message="scope_value is required for api_key and route scopes.",
            )

    async def _assert_no_active_scope_conflict(
        self,
        scope_type: str,
        scope_value: str | None,
        candidate_status: str,
        exclude_id: int | None = None,
    ) -> None:
        """Ensure there is only one active rule for a given scope tuple."""
        if candidate_status != RateLimitRuleStatus.ACTIVE.value:
            return

        existing_rule = await self.rate_limit_rule_repository.get_active_rule_by_scope(
            scope_type=scope_type,
            scope_value=scope_value,
            exclude_id=exclude_id,
        )
        if existing_rule is not None:
            raise ConflictException(
                error_code="RATE_LIMIT_RULE_ALREADY_ACTIVE",
                message="An active rule already exists for this scope.",
            )

    async def create_rule(
        self,
        actor_subject: str,
        payload: RateLimitRuleCreateRequest,
    ) -> RateLimitRuleResponse:
        """Create a new rate limit rule."""
        actor_user = await self._get_actor_user(actor_subject)
        # self._assert_admin_user(actor_user)

        self._validate_scope_tuple(payload.scope_type.value, payload.scope_value)
        await self._assert_no_active_scope_conflict(
            scope_type=payload.scope_type.value,
            scope_value=payload.scope_value,
            candidate_status=payload.status.value,
        )

        rule_input = RateLimitRuleCreateInDB(
            name=payload.name,
            scope_type=payload.scope_type.value,
            scope_value=payload.scope_value,
            algorithm=payload.algorithm.value,
            limit_count=payload.limit_count,
            window_seconds=payload.window_seconds,
            burst_allowance=payload.burst_allowance,
            status=payload.status.value,
            created_by=actor_user.id,
        )

        created_rule = await self.rate_limit_rule_repository.create_rule(rule_input)
        return RateLimitRuleResponse.model_validate(created_rule)

    async def list_rules(
        self,
        actor_subject: str,
        skip: int,
        limit: int,
        scope_type: str | None,
        status: str | None,
    ) -> RateLimitRuleListResponse:
        """List rate limit rules with optional filters."""
        await self._get_actor_user(actor_subject)

        rules = await self.rate_limit_rule_repository.list_rules(
            skip=skip,
            limit=limit,
            scope_type=scope_type,
            status=status,
        )
        total = await self.rate_limit_rule_repository.count_rules(scope_type=scope_type, status=status)

        return RateLimitRuleListResponse(
            items=[RateLimitRuleResponse.model_validate(rule) for rule in rules],
            skip=skip,
            limit=limit,
            total=total,
        )

    async def get_rule(self, actor_subject: str, rule_id: int) -> RateLimitRuleResponse:
        """Retrieve a single rule by id."""
        await self._get_actor_user(actor_subject)

        rule = await self.rate_limit_rule_repository.get_by_id(rule_id)
        if rule is None:
            raise NotFoundException(
                error_code="RATE_LIMIT_RULE_NOT_FOUND",
                message="Rate limit rule not found.",
            )

        return RateLimitRuleResponse.model_validate(rule)

    async def update_rule(
        self,
        actor_subject: str,
        rule_id: int,
        payload: RateLimitRuleUpdateRequest,
    ) -> RateLimitRuleResponse:
        """Update mutable fields of a rule."""
        actor_user = await self._get_actor_user(actor_subject)
        # self._assert_admin_user(actor_user)

        if payload.model_dump(exclude_unset=True) == {}:
            raise BadRequestException(
                error_code="RATE_LIMIT_RULE_INVALID_UPDATE",
                message="At least one updatable field is required.",
            )

        existing_rule = await self.rate_limit_rule_repository.get_by_id(rule_id)
        if existing_rule is None:
            raise NotFoundException(
                error_code="RATE_LIMIT_RULE_NOT_FOUND",
                message="Rate limit rule not found.",
            )

        scope_value_provided = "scope_value" in payload.model_fields_set
        target_scope_type = payload.scope_type.value if payload.scope_type is not None else existing_rule.scope_type
        target_scope_value = payload.scope_value if scope_value_provided else existing_rule.scope_value
        target_status = payload.status.value if payload.status is not None else existing_rule.status

        self._validate_scope_tuple(target_scope_type, target_scope_value)
        await self._assert_no_active_scope_conflict(
            scope_type=target_scope_type,
            scope_value=target_scope_value,
            candidate_status=target_status,
            exclude_id=existing_rule.id,
        )

        update_data = payload.model_dump(exclude_unset=True)
        if "scope_type" in update_data and payload.scope_type is not None:
            update_data["scope_type"] = payload.scope_type.value
        if "algorithm" in update_data and payload.algorithm is not None:
            update_data["algorithm"] = payload.algorithm.value
        if "status" in update_data and payload.status is not None:
            update_data["status"] = payload.status.value

        rule_update = RateLimitRuleUpdateInDB(**update_data)

        updated_rule = await self.rate_limit_rule_repository.update_rule(existing_rule, rule_update)
        return RateLimitRuleResponse.model_validate(updated_rule)

    async def disable_rule(self, actor_subject: str, rule_id: int) -> None:
        """Soft-delete a rule by disabling it."""
        actor_user = await self._get_actor_user(actor_subject)
        # self._assert_admin_user(actor_user)

        existing_rule = await self.rate_limit_rule_repository.get_by_id(rule_id)
        if existing_rule is None:
            raise NotFoundException(
                error_code="RATE_LIMIT_RULE_NOT_FOUND",
                message="Rate limit rule not found.",
            )

        if existing_rule.status == RateLimitRuleStatus.DISABLED.value:
            return

        await self.rate_limit_rule_repository.update_rule(
            existing_rule,
            RateLimitRuleUpdateInDB(status=RateLimitRuleStatus.DISABLED.value),
        )
