import sys
from contextvars import ContextVar, Token
from typing import Any

from loguru import logger

from app.core.config import settings

CORRELATION_ID_CONTEXT: ContextVar[str] = ContextVar("correlation_id", default="-")


def _inject_correlation_id(record: dict[str, Any]) -> None:
    record["extra"]["correlation_id"] = CORRELATION_ID_CONTEXT.get()


def configure_logger() -> None:
    """Configure loguru logger to emit structured JSON logs."""
    logger.remove()
    logger.configure(patcher=_inject_correlation_id)
    logger.add(
        sys.stdout,
        level=settings.LOG_LEVEL.upper(),
        serialize=True,
        backtrace=True,
        diagnose=False,
    )


def set_correlation_id(correlation_id: str) -> Token[str]:
    """Set request correlation ID in context."""
    return CORRELATION_ID_CONTEXT.set(correlation_id)


def reset_correlation_id(token: Token[str]) -> None:
    """Reset request correlation ID context."""
    CORRELATION_ID_CONTEXT.reset(token)
