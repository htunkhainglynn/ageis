"""Generate an ignored local .env file payload with fresh development secrets."""

import base64
import os
import secrets


def fernet_key() -> str:
    """Return a Fernet-compatible URL-safe 32-byte key."""
    return base64.urlsafe_b64encode(os.urandom(32)).decode()


values = {
    "POSTGRES_PASSWORD": secrets.token_hex(24),
    "REDIS_PASSWORD": secrets.token_hex(24),
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
}

for name, value in values.items():
    print(f"{name}={value}")
