import asyncio
import secrets
from collections.abc import AsyncIterator, Awaitable, Callable

import grpc

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.grpc_generated import policy_sync_pb2, policy_sync_pb2_grpc
from app.repositories.ip_block_repository import IPBlockRepository
from app.repositories.jwt_config_repository import JWTConfigRepository
from app.repositories.rate_limit_rule_repository import RateLimitRuleRepository
from app.repositories.threat_rule_repository import ThreatRuleRepository
from app.schemas.proxy_config import ProxyPolicySnapshot
from app.services.proxy_config_service import ProxyConfigService
from app.utils.logger import logger

SnapshotLoader = Callable[[], Awaitable[ProxyPolicySnapshot]]


async def load_proxy_snapshot() -> ProxyPolicySnapshot:
    """Build one policy snapshot in an isolated database session."""
    async with AsyncSessionLocal() as db:
        return await ProxyConfigService(
            jwt_config_repository=JWTConfigRepository(db),
            rate_limit_rule_repository=RateLimitRuleRepository(db),
            ip_block_repository=IPBlockRepository(db),
            threat_rule_repository=ThreatRuleRepository(db),
        ).get_snapshot()


class PolicySyncServicer(policy_sync_pb2_grpc.PolicySyncServicer):
    """Authenticated server-streamed policy snapshots."""

    def __init__(
        self,
        snapshot_loader: SnapshotLoader,
        internal_token: str,
        interval_seconds: float,
    ) -> None:
        self.snapshot_loader = snapshot_loader
        self.internal_token = internal_token
        self.interval_seconds = interval_seconds

    async def Subscribe(
        self,
        request: policy_sync_pb2.SubscribeRequest,
        context: grpc.aio.ServicerContext,
    ) -> AsyncIterator[policy_sync_pb2.PolicySnapshot]:
        del request
        metadata = dict(context.invocation_metadata())
        supplied_token = metadata.get("x-aegis-internal-token", "")
        if not self.internal_token or not secrets.compare_digest(
            supplied_token, self.internal_token
        ):
            await context.abort(grpc.StatusCode.UNAUTHENTICATED, "internal authentication failed")

        while not context.done():
            snapshot = await self.snapshot_loader()
            yield policy_sync_pb2.PolicySnapshot(
                json_payload=snapshot.model_dump_json().encode()
            )
            await asyncio.sleep(self.interval_seconds)


async def start_policy_grpc_server(
    snapshot_loader: SnapshotLoader = load_proxy_snapshot,
    host: str | None = None,
    port: int | None = None,
    internal_token: str | None = None,
    interval_seconds: float | None = None,
) -> tuple[grpc.aio.Server, int]:
    """Start the internal policy stream and return its bound port."""
    server = grpc.aio.server()
    policy_sync_pb2_grpc.add_PolicySyncServicer_to_server(
        PolicySyncServicer(
            snapshot_loader=snapshot_loader,
            internal_token=internal_token
            if internal_token is not None
            else settings.INTERNAL_API_TOKEN,
            interval_seconds=interval_seconds
            if interval_seconds is not None
            else settings.GRPC_SYNC_INTERVAL_SECONDS,
        ),
        server,
    )
    bind_host = host if host is not None else settings.GRPC_HOST
    bind_port = port if port is not None else settings.GRPC_PORT
    bound_port = server.add_insecure_port(f"{bind_host}:{bind_port}")
    if bound_port == 0:
        raise RuntimeError("gRPC policy server failed to bind")
    await server.start()
    logger.info("Policy gRPC server started on {}:{}", bind_host, bound_port)
    return server, bound_port
