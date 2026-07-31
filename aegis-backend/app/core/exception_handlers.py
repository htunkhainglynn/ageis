from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.exceptions import AppException
from app.schemas.base import ErrorResponse
from app.utils.logger import logger


def _build_error_response(error_code: str, message: str, status_code: int) -> JSONResponse:
    """Build a consistent API error response payload."""
    payload = ErrorResponse(errorCode=error_code, message=message)
    return JSONResponse(status_code=status_code, content=payload.model_dump(mode="json"))


def register_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers."""

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        """Handle known application exceptions."""
        logger.bind(path=request.url.path, method=request.method, error_code=exc.error_code).opt(
            exception=exc
        ).error("Application error: {}", exc.message)
        return _build_error_response(exc.error_code, exc.message, exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        """Handle request payload validation errors."""
        logger.bind(path=request.url.path, method=request.method, errors=exc.errors()).opt(
            exception=exc
        ).error("Validation error")
        return _build_error_response(
            error_code="REQUEST_VALIDATION_ERROR",
            message="Invalid request payload.",
            status_code=422,
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, _: Exception) -> JSONResponse:
        """Handle unexpected errors and return a safe payload."""
        logger.bind(path=request.url.path, method=request.method).exception("Unhandled server error")
        return _build_error_response(
            error_code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred.",
            status_code=500,
        )
