from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.bootstrap import bootstrap_from_environment
from app.core.database import check_database_health, close_database, init_database
from app.core.exception_handlers import register_exception_handlers
from app.core.redis import check_redis_health, close_redis, init_redis
from app.middlewares.logging import CorrelationIdMiddleware, RequestLoggingMiddleware
from app.grpc_server import start_policy_grpc_server
from app.routers.base import api_router
from app.schemas.base import ApiResponse, success_response
from app.schemas.health import HealthStatusData
from app.utils.logger import configure_logger, logger

configure_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown lifecycle."""
    app.state.database_ready = await init_database()
    app.state.redis_ready = await init_redis()
    if app.state.database_ready:
        await bootstrap_from_environment()
    grpc_server = None
    if (
        app.state.database_ready
        and settings.GRPC_ENABLED
        and settings.INTERNAL_API_TOKEN.strip()
    ):
        grpc_server, _ = await start_policy_grpc_server()

    if not app.state.database_ready:
        logger.warning("Application started without database connectivity")
    if not app.state.redis_ready:
        logger.warning("Application started without Redis connectivity")

    yield

    if grpc_server is not None:
        await grpc_server.stop(grace=5)
    await close_database()
    await close_redis()


app = FastAPI(
    title=settings.app.NAME,
    debug=settings.app.DEBUG,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.app.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(CorrelationIdMiddleware)

register_exception_handlers(app)
app.include_router(api_router)


@app.get(
    "/health",
    response_model=ApiResponse[HealthStatusData],
    tags=["Health"],
    summary="Health check",
    description="Check service, database, and Redis dependency status.",
)
async def health_check() -> ApiResponse[HealthStatusData]:
    """Health check.

    Report application, database, and Redis health status.
    """
    database_ok = await check_database_health()
    redis_ok = await check_redis_health()

    health_data = HealthStatusData(
        service="up",
        database="up" if database_ok else "down",
        redis="up" if redis_ok else "down",
    )
    return success_response(message="Health check completed.", data=health_data)
