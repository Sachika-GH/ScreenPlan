"""Health check route."""
from flask import Blueprint, jsonify

from database import db_connection, get_uptime
from config import VERSION

health_bp = Blueprint("health", __name__)


@health_bp.route("/api/health", methods=["GET"])
def health():
    with db_connection() as conn:
        user_count = conn.execute("SELECT COUNT(*) as cnt FROM user").fetchone()["cnt"]

    return jsonify({
        "status": "ok",
        "version": VERSION,
        "uptime_seconds": round(get_uptime(), 1),
        "user_count": user_count,
    }), 200
