"""
protocol_models.py - Shared data models for ScreenPlan Windows Agent.
Mirror of the backend's protocol definitions.
"""
from datetime import date, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class AppCategory(str, Enum):
    LEARNING = "learning"
    ENTERTAINMENT = "entertainment"
    OTHER = "other"


class Platform(str, Enum):
    MACOS = "macos"
    WINDOWS = "windows"
    IOS = "ios"


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    family_id: int
    display_name: str


class DeviceResponse(BaseModel):
    id: int
    name: str
    platform: str
    registered_at: datetime


class TimelineEvent(BaseModel):
    app_name: str = Field(..., min_length=1, max_length=128)
    category: AppCategory
    timestamp: datetime


class TimelineUploadRequest(BaseModel):
    device_id: int
    events: list[TimelineEvent] = Field(..., min_items=1, max_items=500)


class ScheduleResponse(BaseModel):
    id: int
    user_id: int
    date: date
    plan_markdown: str
    generated_at: datetime


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    uptime_seconds: float
    user_count: int


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
