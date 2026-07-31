import json

import grpc
import pytest

from app.grpc_generated import policy_sync_pb2, policy_sync_pb2_grpc
from app.grpc_server import start_policy_grpc_server
from app.schemas.proxy_config import ProxyPolicySnapshot

pytestmark = pytest.mark.asyncio


async def test_grpc_policy_stream_authenticates_and_delivers_snapshot() -> None:
    """Verify a real gRPC client receives the same enforcement snapshot shape."""

    async def snapshot_loader() -> ProxyPolicySnapshot:
        return ProxyPolicySnapshot(
            jwt=None,
            rate_limit_rules=[],
            blocked_ip_addresses=["203.0.113.90"],
            threat_rules=[],
        )

    server, port = await start_policy_grpc_server(
        snapshot_loader=snapshot_loader,
        host="127.0.0.1",
        port=0,
        internal_token="grpc-test-token",
        interval_seconds=0.01,
    )
    try:
        async with grpc.aio.insecure_channel(f"127.0.0.1:{port}") as channel:
            stub = policy_sync_pb2_grpc.PolicySyncStub(channel)
            stream = stub.Subscribe(
                policy_sync_pb2.SubscribeRequest(),
                metadata=(("x-aegis-internal-token", "grpc-test-token"),),
            )
            message = await stream.read()
            payload = json.loads(message.json_payload)
            assert payload["blocked_ip_addresses"] == ["203.0.113.90"]
            stream.cancel()
    finally:
        await server.stop(grace=0)


async def test_grpc_policy_stream_rejects_invalid_internal_token() -> None:
    async def snapshot_loader() -> ProxyPolicySnapshot:
        return ProxyPolicySnapshot(
            jwt=None,
            rate_limit_rules=[],
            blocked_ip_addresses=[],
            threat_rules=[],
        )

    server, port = await start_policy_grpc_server(
        snapshot_loader=snapshot_loader,
        host="127.0.0.1",
        port=0,
        internal_token="grpc-test-token",
        interval_seconds=1,
    )
    try:
        async with grpc.aio.insecure_channel(f"127.0.0.1:{port}") as channel:
            stub = policy_sync_pb2_grpc.PolicySyncStub(channel)
            stream = stub.Subscribe(
                policy_sync_pb2.SubscribeRequest(),
                metadata=(("x-aegis-internal-token", "wrong"),),
            )
            with pytest.raises(grpc.aio.AioRpcError) as error:
                await stream.read()
            assert error.value.code() == grpc.StatusCode.UNAUTHENTICATED
    finally:
        await server.stop(grace=0)
