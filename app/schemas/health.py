from pydantic import BaseModel, ConfigDict
from datetime import datetime
from enum import Enum


class ServiceStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class HealthCheck(BaseModel):
    status: ServiceStatus
    timestamp: datetime
    version: str
    uptime_seconds: float

    model_config = ConfigDict(from_attributes=True)


class DatabaseHealth(BaseModel):
    status: ServiceStatus
    connection_pool_size: int
    active_connections: int
    latency_ms: float

    model_config = ConfigDict(from_attributes=True)


class FullHealthResponse(BaseModel):
    overall: HealthCheck
    database: DatabaseHealth

    model_config = ConfigDict(from_attributes=True)
