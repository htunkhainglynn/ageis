from app.core.encryption import decrypt_jwt_signing_key
from app.models.jwt_config import JWTConfigAlgorithm
from app.repositories.ip_block_repository import IPBlockRepository
from app.repositories.jwt_config_repository import JWTConfigRepository
from app.repositories.rate_limit_rule_repository import RateLimitRuleRepository
from app.repositories.threat_rule_repository import ThreatRuleRepository
from app.repositories.route_permission_repository import RoutePermissionRepository
from app.schemas.proxy_config import (
    ProxyJWTValidationPolicy,
    ProxyPolicySnapshot,
    ProxyRateLimitPolicy,
    ProxyThreatPolicy,
    ProxyRoutePermissionPolicy,
)


class ProxyConfigService:
    """Build trusted policy snapshots for the reverse proxy."""

    def __init__(
        self,
        jwt_config_repository: JWTConfigRepository,
        rate_limit_rule_repository: RateLimitRuleRepository,
        ip_block_repository: IPBlockRepository,
        threat_rule_repository: ThreatRuleRepository,
        route_permission_repository: RoutePermissionRepository,
    ) -> None:
        self.jwt_config_repository = jwt_config_repository
        self.rate_limit_rule_repository = rate_limit_rule_repository
        self.ip_block_repository = ip_block_repository
        self.threat_rule_repository = threat_rule_repository
        self.route_permission_repository = route_permission_repository

    async def get_snapshot(self) -> ProxyPolicySnapshot:
        """Return active JWT and rate-limit policies in one consistent shape."""
        jwt_config = await self.jwt_config_repository.get_active_config()
        rate_limit_rules = await self.rate_limit_rule_repository.list_active_rules()
        ip_blocks = await self.ip_block_repository.list_active_blocks()
        threat_rules = await self.threat_rule_repository.list_active_rules()
        route_permissions = await self.route_permission_repository.list_active_permissions()

        jwt_policy: ProxyJWTValidationPolicy | None = None
        if jwt_config is not None:
            verification_key = (
                decrypt_jwt_signing_key(jwt_config.signing_key)
                if jwt_config.algorithm == JWTConfigAlgorithm.HS256.value
                else jwt_config.public_key
            )
            if verification_key is not None:
                jwt_policy = ProxyJWTValidationPolicy(
                    id=jwt_config.id,
                    algorithm=jwt_config.algorithm,
                    verification_key=verification_key,
                    issuer=jwt_config.issuer,
                    audience=jwt_config.audience,
                )

        return ProxyPolicySnapshot(
            jwt=jwt_policy,
            rate_limit_rules=[
                ProxyRateLimitPolicy(
                    id=rule.id,
                    scope_type=rule.scope_type,
                    scope_value=rule.scope_value,
                    algorithm=rule.algorithm,
                    limit_count=rule.limit_count,
                    window_seconds=rule.window_seconds,
                    burst_allowance=rule.burst_allowance,
                )
                for rule in rate_limit_rules
            ],
            blocked_ip_addresses=[block.ip_address for block in ip_blocks],
            threat_rules=[
                ProxyThreatPolicy(
                    id=rule.id, name=rule.name, pattern=rule.pattern, severity=rule.severity
                )
                for rule in threat_rules
            ],
            route_permissions=[
                ProxyRoutePermissionPolicy(
                    id=permission.id,
                    method=permission.method,
                    path_pattern=permission.path_pattern,
                    required_scope=permission.required_scope,
                )
                for permission in route_permissions
            ],
        )
