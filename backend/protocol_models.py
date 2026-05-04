"""Shared protocol models - mirror of screenplan-protocol."""
from datetime import date, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class AppCategory(str, Enum):
    LEARNING = "learning"
    ENTERTAINMENT = "entertainment"
    OTHER = "other"


class Platform(str, Enum):
    MACOS = "macos"
    WINDOWS = "windows"
    IOS = "ios"
    ANDROID = "android"
    LINUX = "linux"


class UserRegisterRequest(BaseModel):
    family_name: str = Field(..., min_length=1, max_length=64)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)
    display_name: str = Field(..., min_length=1, max_length=64)


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    family_id: int
    display_name: str


class DeviceRegisterRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    platform: Platform

class DeviceUpdateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)

class DeviceResponse(BaseModel):
    id: int
    name: str
    platform: str
    registered_at: datetime


class UsageRecord(BaseModel):
    app_name: str = Field(..., min_length=1, max_length=128)
    category: AppCategory
    duration_minutes: float = Field(..., ge=0)


class UsageUploadRequest(BaseModel):
    device_id: int
    date: date
    records: list[UsageRecord] = Field(..., min_items=1, max_items=5000)


class UsageSummaryPerApp(BaseModel):
    app_name: str
    category: str
    total_minutes: float
    record_count: int


class UsageSummaryPerDevice(BaseModel):
    device_id: int
    device_name: str
    platform: str
    total_minutes: float
    learning_pct: float
    entertainment_pct: float
    other_pct: float
    switch_count: int
    longest_focus_minutes: float
    top_apps: list[UsageSummaryPerApp]


class UsageSummaryResponse(BaseModel):
    user_id: int
    date: date
    total_minutes_all_devices: float
    overlap_minutes: float = 0.0
    devices: list[UsageSummaryPerDevice]


class ScheduleGenerateRequest(BaseModel):
    date: Optional[date] = None
    include_calendar: bool = False
    message: Optional[str] = None


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


class TimelineEvent(BaseModel):
    app_name: str = Field(..., min_length=1, max_length=128)
    category: AppCategory
    timestamp: datetime


class TimelineUploadRequest(BaseModel):
    device_id: int
    events: list[TimelineEvent] = Field(..., min_items=1, max_items=500)


class TimelineEventResponse(BaseModel):
    id: int
    device_id: int
    timestamp: datetime
    app_name: str
    category: str


class TimelineResponse(BaseModel):
    user_id: int
    device_id: Optional[int] = None
    date: date
    events: list[TimelineEventResponse]


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None


# ─── Friends ──────────────────────────────────────────────────────

class FriendRequestSend(BaseModel):
    email: EmailStr


class FriendRequestResponse(BaseModel):
    id: int
    from_user_id: int
    from_display_name: str
    from_email: str
    status: str
    created_at: datetime


class FriendResponse(BaseModel):
    id: int
    friend_id: int
    display_name: str
    email: str
    share_usage: bool
    share_schedule: bool


class FriendShareUpdate(BaseModel):
    share_usage: Optional[bool] = None
    share_schedule: Optional[bool] = None


# ─── Enhanced Timeline for Web UI ─────────────────────────────────

class TimelineDeviceSummary(BaseModel):
    device_id: int
    device_name: str
    platform: str
    event_count: int
    events: list[TimelineEventResponse]


class FullTimelineResponse(BaseModel):
    user_id: int
    date: date
    devices: list[TimelineDeviceSummary]
