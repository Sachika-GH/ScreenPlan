"""API Blueprint registration."""
from flask import Blueprint

from .auth_routes import auth_bp
from .device_routes import device_bp
from .usage_routes import usage_bp
from .schedule_routes import schedule_bp
from .health_routes import health_bp
from .friend_routes import friend_bp


__all__ = ["auth_bp", "device_bp", "usage_bp", "schedule_bp", "health_bp", "friend_bp"]
