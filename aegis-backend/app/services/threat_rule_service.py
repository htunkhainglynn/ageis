from app.core.exceptions import BadRequestException, ForbiddenException, NotFoundException
from app.models.threat_rule import ThreatRuleStatus
from app.models.user import User, UserRole
from app.repositories.threat_rule_repository import ThreatRuleRepository
from app.schemas.threat_rule import (
    ThreatRuleCreateInDB, ThreatRuleCreateRequest, ThreatRuleListResponse,
    ThreatRuleResponse, ThreatRuleUpdateInDB, ThreatRuleUpdateRequest,
)


class ThreatRuleService:
    def __init__(self, repository: ThreatRuleRepository) -> None:
        self.repository = repository

    @staticmethod
    def _assert_admin(actor: User) -> None:
        if actor.role != UserRole.ADMIN.value:
            raise ForbiddenException("THREAT_RULE_FORBIDDEN", "You cannot manage threat rules.")

    async def create(self, actor: User, payload: ThreatRuleCreateRequest) -> ThreatRuleResponse:
        self._assert_admin(actor)
        rule = await self.repository.create_rule(ThreatRuleCreateInDB(
            name=payload.name, pattern=payload.pattern, severity=payload.severity.value,
            status=payload.status.value, created_by=actor.id,
        ))
        return ThreatRuleResponse.model_validate(rule)

    async def list(self, actor: User, skip: int, limit: int, status: str | None) -> ThreatRuleListResponse:
        self._assert_admin(actor)
        rules = await self.repository.list_rules(skip, limit, status)
        return ThreatRuleListResponse(
            items=[ThreatRuleResponse.model_validate(rule) for rule in rules],
            skip=skip, limit=limit, total=await self.repository.count_rules(status),
        )

    async def get(self, actor: User, rule_id: int) -> ThreatRuleResponse:
        self._assert_admin(actor)
        rule = await self.repository.get_by_id(rule_id)
        if rule is None:
            raise NotFoundException("THREAT_RULE_NOT_FOUND", "Threat rule not found.")
        return ThreatRuleResponse.model_validate(rule)

    async def update(self, actor: User, rule_id: int, payload: ThreatRuleUpdateRequest) -> ThreatRuleResponse:
        self._assert_admin(actor)
        data = payload.model_dump(exclude_unset=True)
        if not data:
            raise BadRequestException("THREAT_RULE_INVALID_UPDATE", "At least one field is required.")
        rule = await self.repository.get_by_id(rule_id)
        if rule is None:
            raise NotFoundException("THREAT_RULE_NOT_FOUND", "Threat rule not found.")
        for field in ("severity", "status"):
            value = getattr(payload, field)
            if field in data and value is not None:
                data[field] = value.value
        updated = await self.repository.update_rule(rule, ThreatRuleUpdateInDB(**data))
        return ThreatRuleResponse.model_validate(updated)

    async def disable(self, actor: User, rule_id: int) -> None:
        self._assert_admin(actor)
        rule = await self.repository.get_by_id(rule_id)
        if rule is None:
            raise NotFoundException("THREAT_RULE_NOT_FOUND", "Threat rule not found.")
        if rule.status != ThreatRuleStatus.DISABLED.value:
            await self.repository.update_rule(
                rule, ThreatRuleUpdateInDB(status=ThreatRuleStatus.DISABLED.value)
            )
