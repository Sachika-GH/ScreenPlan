"""Device management routes."""
from functools import wraps
from flask import Blueprint, request, jsonify, g

from database import db_connection
from auth import decode_access_token
from protocol_models import DeviceRegisterRequest, DeviceUpdateRequest, DeviceResponse

device_bp = Blueprint("device", __name__, url_prefix="/api/devices")


def require_auth(f):
    """Decorator to require JWT authentication."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "未认证"}), 401
        token = auth_header.split(" ", 1)[1]
        payload = decode_access_token(token)
        if not payload:
            return jsonify({"error": "Token 无效或已过期"}), 401
        g.user_id = int(payload["sub"])
        g.family_id = int(payload["family_id"])
        return f(*args, **kwargs)
    return decorated


@device_bp.route("", methods=["GET"])
@require_auth
def list_devices():
    with db_connection() as conn:
        rows = conn.execute(
            "SELECT id, name, platform, registered_at FROM device WHERE user_id = ? ORDER BY id",
            (g.user_id,),
        ).fetchall()

    devices = [
        DeviceResponse(
            id=r["id"],
            name=r["name"],
            platform=r["platform"],
            registered_at=r["registered_at"],
        ).model_dump()
        for r in rows
    ]
    return jsonify(devices), 200


@device_bp.route("", methods=["POST"])
@require_auth
def register_device():
    body = request.get_json(silent=True)
    if not body:
        return jsonify({"error": "Invalid JSON"}), 400

    try:
        data = DeviceRegisterRequest(**body)
    except Exception as e:
        return jsonify({"error": str(e)}), 422

    platform_val = data.platform.value if hasattr(data.platform, "value") else data.platform

    with db_connection() as conn:
        existing = conn.execute(
            "SELECT id, name, platform, registered_at FROM device WHERE user_id = ? AND name = ? AND platform = ?",
            (g.user_id, data.name, platform_val),
        ).fetchone()

        if existing:
            resp = DeviceResponse(
                id=existing["id"],
                name=existing["name"],
                platform=existing["platform"],
                registered_at=existing["registered_at"],
            )
            return jsonify(resp.model_dump()), 200

        cur = conn.execute(
            "INSERT INTO device (user_id, name, platform) VALUES (?, ?, ?)",
            (g.user_id, data.name, platform_val),
        )
        conn.commit()
        device_id = cur.lastrowid
        row = conn.execute("SELECT * FROM device WHERE id = ?", (device_id,)).fetchone()

    resp = DeviceResponse(
        id=row["id"],
        name=row["name"],
        platform=row["platform"],
        registered_at=row["registered_at"],
    )
    return jsonify(resp.model_dump()), 201


@device_bp.route("/<int:device_id>", methods=["PUT"])
@require_auth
def update_device(device_id):
    body = request.get_json(silent=True)
    if not body:
        return jsonify({"error": "Invalid JSON"}), 400

    try:
        data = DeviceUpdateRequest(**body)
    except Exception as e:
        return jsonify({"error": str(e)}), 422

    with db_connection() as conn:
        device = conn.execute(
            "SELECT id, name, platform FROM device WHERE id = ? AND user_id = ?",
            (device_id, g.user_id),
        ).fetchone()
        if not device:
            return jsonify({"error": "设备不存在"}), 404

        conflict = conn.execute(
            "SELECT id FROM device WHERE user_id = ? AND name = ? AND platform = ? AND id != ?",
            (g.user_id, data.name, device["platform"], device_id),
        ).fetchone()
        if conflict:
            return jsonify({"error": "同名同平台设备已存在"}), 409

        conn.execute(
            "UPDATE device SET name = ? WHERE id = ?",
            (data.name, device_id),
        )
        conn.commit()

        row = conn.execute("SELECT * FROM device WHERE id = ?", (device_id,)).fetchone()

    resp = DeviceResponse(
        id=row["id"],
        name=row["name"],
        platform=row["platform"],
        registered_at=row["registered_at"],
    )
    return jsonify(resp.model_dump()), 200


@device_bp.route("/<int:device_id>", methods=["DELETE"])
@require_auth
def delete_device(device_id):
    with db_connection() as conn:
        device = conn.execute(
            "SELECT id FROM device WHERE id = ? AND user_id = ?",
            (device_id, g.user_id),
        ).fetchone()
        if not device:
            return jsonify({"error": "设备不存在"}), 404

        conn.execute("DELETE FROM usage_record WHERE device_id = ?", (device_id,))
        conn.execute("DELETE FROM timeline_event WHERE device_id = ?", (device_id,))
        conn.execute("DELETE FROM device WHERE id = ?", (device_id,))
        conn.commit()
    return jsonify({"detail": "deleted"}), 200
