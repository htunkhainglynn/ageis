"""Generate an ignored local .env file payload with fresh development secrets."""

import base64
import os
import secrets
import shlex
import subprocess


def fernet_key() -> str:
    """Return a Fernet-compatible URL-safe 32-byte key."""
    return base64.urlsafe_b64encode(os.urandom(32)).decode()


def container_env(container_name: str, env_name: str) -> str | None:
    """Reuse local Docker credentials when an existing dev volume is present."""
    try:
        result = subprocess.run(
            ["docker", "inspect", container_name, "--format", "{{range .Config.Env}}{{println .}}{{end}}"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None

    prefix = f"{env_name}="
    for line in result.stdout.splitlines():
        if line.startswith(prefix):
            return line.removeprefix(prefix)
    return None


values = {
    "POSTGRES_PASSWORD": container_env("aegis-postgres-1", "POSTGRES_PASSWORD") or secrets.token_hex(24),
    "REDIS_PASSWORD": container_env("aegis-redis-1", "REDIS_PASSWORD") or secrets.token_hex(24),
    "JWT_SECRET_KEY": secrets.token_hex(32),
    "JWT_CONFIG_ENCRYPTION_KEY": fernet_key(),
    "INTERNAL_API_TOKEN": secrets.token_hex(32),
    "BOOTSTRAP_ADMIN_EMAILS": "admin@aegis.local",
    "BOOTSTRAP_ADMIN_PASSWORD": f"Aa1!{secrets.token_hex(12)}",
    "BOOTSTRAP_ADMIN_FULL_NAME": "Aegis Administrator",
    "POSTGRES_PORT": "5432",
    "REDIS_PORT": "6379",
    "CONTROL_PLANE_PORT": "8000",
    "PROXY_PORT": "8080",
    "DASHBOARD_PORT": "3000",
    "UPSTREAM_PORT": "9000",
    "GRPC_SYNC_INTERVAL_SECONDS": "2",
    "GRPC_RECONNECT_DELAY": "1s",
    "AUTO_IP_BLOCK_ENABLED": "true",
    "AUTO_IP_BLOCK_THRESHOLD": "5",
    "AUTO_IP_BLOCK_WINDOW_SECONDS": "300",
}

for name, value in values.items():
    print(f"{name}={shlex.quote(value)}")
