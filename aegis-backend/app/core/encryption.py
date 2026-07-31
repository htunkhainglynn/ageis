from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings
from app.core.exceptions import BadRequestException


def _build_jwt_config_cipher() -> Fernet:
    """Build the JWT-configuration cipher from environment-backed material."""
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


def encrypt_jwt_signing_key(signing_key: str) -> str:
    """Encrypt JWT signing key material for database persistence."""
    return _build_jwt_config_cipher().encrypt(signing_key.encode()).decode()


def decrypt_jwt_signing_key(encrypted_signing_key: str) -> str:
    """Decrypt JWT signing key material for trusted enforcement use."""
    try:
        return _build_jwt_config_cipher().decrypt(encrypted_signing_key.encode()).decode()
    except InvalidToken as exc:
        raise BadRequestException(
            error_code="JWT_CONFIG_SIGNING_KEY_DECRYPT_FAILED",
            message="Unable to decrypt stored signing key.",
        ) from exc
