from pydantic import BaseModel


class HealthStatusData(BaseModel):
    """Health-check status payload for service dependencies."""

    service: str
    database: str
    redis: str
