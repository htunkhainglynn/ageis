"""Shared constants and helpers for Aegis development-data tools only."""

from __future__ import annotations

import os
import secrets
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "aegis-backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

DEV_ENVIRONMENT = "development"

ADMIN_EMAIL = "admin@aegis.local"
VIEWER_EMAIL = "viewer@aegis.local"
CONSUMER1_EMAIL = "consumer1@aegis.local"
CONSUMER2_EMAIL = "consumer2@aegis.local"

CONSUMER1_ACTIVE_KEY_NAME = "DEV SEED - consumer1 active"
CONSUMER1_REVOKED_KEY_NAME = "DEV SEED - consumer1 revoked"
CONSUMER2_ACTIVE_KEY_NAME = "DEV SEED - consumer2 active"
DEV_API_KEY_NAMES = (
    CONSUMER1_ACTIVE_KEY_NAME,
    CONSUMER1_REVOKED_KEY_NAME,
    CONSUMER2_ACTIVE_KEY_NAME,
)

GLOBAL_RULE_NAME = "DEV SEED - global default"
CONSUMER1_RULE_NAME = "DEV SEED - consumer1 demonstration limit"
ECHO_ROUTE_RULE_NAME = "DEV SEED - echo route"
DEV_RATE_RULE_NAMES = (
    GLOBAL_RULE_NAME,
    CONSUMER1_RULE_NAME,
    ECHO_ROUTE_RULE_NAME,
)

JWT_CONFIG_NAME = "DEV SEED - echo service HS256"
JWT_ISSUER = "aegis-dev"
JWT_AUDIENCE = "aegis-echo-service"

_FALLBACK_ADMIN_PASSWORD = "DEV-ONLY-Admin!ChangeMe"
_FALLBACK_USER_PASSWORD = "DEV-ONLY-User!ChangeMe"


@dataclass(frozen=True)
class DevSecrets:
    """Runtime-only credentials used to create deterministic development data."""

    admin_password: str
    user_password: str
    consumer1_active_key: str
    consumer1_revoked_key: str
    consumer2_active_key: str
    jwt_signing_key: str
    fallback_variables: tuple[str, ...]

    @classmethod
    def from_environment(cls) -> "DevSecrets":
        """Load passwords and create runtime-only keys unless explicitly overridden."""
        fallbacks: list[str] = []
        password_values: list[str] = []
        for variable, fallback in (
            ("AEGIS_DEV_ADMIN_PASSWORD", _FALLBACK_ADMIN_PASSWORD),
            ("AEGIS_DEV_USER_PASSWORD", _FALLBACK_USER_PASSWORD),
        ):
            value = os.getenv(variable)
            if value is None or value == "":
                value = fallback
                fallbacks.append(variable)
            password_values.append(value)

        api_keys = [
            os.getenv(variable) or f"ak_{secrets.token_urlsafe(32)}"
            for variable in (
                "AEGIS_DEV_CONSUMER1_ACTIVE_KEY",
                "AEGIS_DEV_CONSUMER1_REVOKED_KEY",
                "AEGIS_DEV_CONSUMER2_ACTIVE_KEY",
            )
        ]
        jwt_signing_key = os.getenv("AEGIS_DEV_JWT_SIGNING_KEY") or secrets.token_urlsafe(
            48
        )

        dev_secrets = cls(
            admin_password=password_values[0],
            user_password=password_values[1],
            consumer1_active_key=api_keys[0],
            consumer1_revoked_key=api_keys[1],
            consumer2_active_key=api_keys[2],
            jwt_signing_key=jwt_signing_key,
            fallback_variables=tuple(fallbacks),
        )
        dev_secrets.validate()
        return dev_secrets

    def validate(self) -> None:
        """Reject malformed values before any database transaction starts."""
        if len(self.admin_password) < 12 or len(self.user_password) < 12:
            raise ValueError("Development passwords must contain at least 12 characters.")

        for raw_key in (
            self.consumer1_active_key,
            self.consumer1_revoked_key,
            self.consumer2_active_key,
        ):
            encoded_length = len(raw_key.encode())
            if not raw_key.startswith("ak_") or not 8 <= encoded_length <= 72:
                raise ValueError(
                    "Development API keys must start with 'ak_' and contain 8-72 bytes."
                )

        if len(self.jwt_signing_key.encode()) < 32:
            raise ValueError("The development HS256 signing key must contain at least 32 bytes.")


def require_development_environment(app_environment: str | None = None) -> None:
    """Refuse execution unless both the explicit and application environments are dev."""
    explicit_environment = os.getenv("ENVIRONMENT", "").strip().lower()
    resolved_app_environment = (
        app_environment if app_environment is not None else os.getenv("APP_ENV", "")
    ).strip().lower()

    if explicit_environment != DEV_ENVIRONMENT:
        raise RuntimeError(
            "Refusing to access seed data: set ENVIRONMENT=development explicitly."
        )
    if resolved_app_environment != DEV_ENVIRONMENT:
        raise RuntimeError(
            "Refusing to access seed data: APP_ENV must also resolve to development."
        )


def print_fallback_warning(variable_names: Iterable[str]) -> None:
    """Print a prominent warning when known dev-only credential fallbacks are active."""
    names = tuple(variable_names)
    if not names:
        return
    border = "!" * 78
    print(border, file=sys.stderr)
    print("WARNING: INSECURE DEV-ONLY FALLBACK CREDENTIALS ARE IN USE.", file=sys.stderr)
    print("NEVER RUN THIS DATASET OR THESE CREDENTIALS IN PRODUCTION.", file=sys.stderr)
    print(f"Fallback variables: {', '.join(names)}", file=sys.stderr)
    print(border, file=sys.stderr)


def mask_secret(value: str) -> str:
    """Match the Control Plane's operator-facing secret masking convention."""
    return "****" if value == "" else f"****{value[-4:]}"


def format_table(headers: Sequence[str], rows: Sequence[Sequence[object]]) -> str:
    """Return a small dependency-free text table."""
    string_rows = [[str(cell) if cell is not None else "-" for cell in row] for row in rows]
    widths = [
        max(len(header), *(len(row[index]) for row in string_rows))
        for index, header in enumerate(headers)
    ]

    def format_row(row: Sequence[str]) -> str:
        return " | ".join(cell.ljust(widths[index]) for index, cell in enumerate(row))

    separator = "-+-".join("-" * width for width in widths)
    return "\n".join(
        [format_row(list(headers)), separator, *(format_row(row) for row in string_rows)]
    )
