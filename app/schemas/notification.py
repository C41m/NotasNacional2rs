from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from enum import Enum
from typing import Optional


class NotificationType(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    SUCCESS = "success"


class NotificationPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class NotificationBase(BaseModel):
    title: str = Field(..., max_length=255)
    message: str
    type: NotificationType = NotificationType.INFO
    priority: NotificationPriority = NotificationPriority.MEDIUM
    user_id: Optional[int] = None
    company_id: Optional[int] = None
    read: bool = False


class NotificationCreate(NotificationBase):
    pass


class NotificationUpdate(BaseModel):
    read: bool | None = None
    priority: NotificationPriority | None = None


class NotificationOut(BaseModel):
    id: int
    title: str
    message: str
    type: NotificationType
    priority: NotificationPriority
    user_id: int | None = None
    company_id: int | None = None
    read: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationListOut(BaseModel):
    notifications: list[NotificationOut]
    total: int
    unread_count: int

    model_config = ConfigDict(from_attributes=True)
