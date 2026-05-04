"""Friend management routes."""
from datetime import date, datetime

from flask import Blueprint, request, jsonify, g

from database import db_connection
from protocol_models import FriendRequestSend, FriendShareUpdate
from api.device_routes import require_auth

friend_bp = Blueprint("friend", __name__, url_prefix="/api/friends")


@friend_bp.route("/request", methods=["POST"])
@require_auth
def send_request():
    body = request.get_json(silent=True)
    if not body:
        return jsonify({"error": "Invalid JSON"}), 400
    try:
        data = FriendRequestSend(**body)
    except Exception as e:
        return jsonify({"error": str(e)}), 422

    with db_connection() as conn:
        to_user = conn.execute("SELECT id FROM user WHERE email = ?", (data.email,)).fetchone()
        if not to_user:
            return jsonify({"error": "未找到该用户"}), 404
        if to_user["id"] == g.user_id:
            return jsonify({"error": "不能添加自己为好友"}), 400

        existing = conn.execute(
            "SELECT id, status FROM friend_request WHERE from_user_id=? AND to_user_id=? AND status='pending'",
            (g.user_id, to_user["id"]),
        ).fetchone()
        if existing:
            return jsonify({"error": "已发送过请求"}), 409

        conn.execute(
            "INSERT INTO friend_request (from_user_id, to_user_id) VALUES (?, ?)",
            (g.user_id, to_user["id"]),
        )
        conn.commit()

    return jsonify({"detail": "请求已发送"}), 201


@friend_bp.route("/requests", methods=["GET"])
@require_auth
def list_requests():
    with db_connection() as conn:
        received = conn.execute(
            "SELECT fr.id, fr.from_user_id, u.display_name, u.email, fr.status, fr.created_at "
            "FROM friend_request fr JOIN user u ON fr.from_user_id = u.id "
            "WHERE fr.to_user_id = ? AND fr.status = 'pending' "
            "ORDER BY fr.created_at DESC",
            (g.user_id,),
        ).fetchall()

        sent = conn.execute(
            "SELECT fr.id, fr.to_user_id as from_user_id, u.display_name, u.email, fr.status, fr.created_at "
            "FROM friend_request fr JOIN user u ON fr.to_user_id = u.id "
            "WHERE fr.from_user_id = ? AND fr.status = 'pending' "
            "ORDER BY fr.created_at DESC",
            (g.user_id,),
        ).fetchall()

    def format_rows(rows):
        return [
            {
                "id": r["id"],
                "user_id": r["from_user_id"],
                "display_name": r["display_name"],
                "email": r["email"],
                "status": r["status"],
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    return jsonify({"received": format_rows(received), "sent": format_rows(sent)}), 200


@friend_bp.route("/accept/<int:request_id>", methods=["POST"])
@require_auth
def accept_request(request_id):
    with db_connection() as conn:
        req = conn.execute(
            "SELECT id, from_user_id, to_user_id, status FROM friend_request WHERE id=?",
            (request_id,),
        ).fetchone()
        if not req:
            return jsonify({"error": "请求不存在"}), 404
        if req["to_user_id"] != g.user_id:
            return jsonify({"error": "无权操作"}), 403
        if req["status"] != "pending":
            return jsonify({"error": "请求已处理"}), 409

        conn.execute(
            "UPDATE friend_request SET status='accepted' WHERE id=?", (request_id,)
        )
        # Create bidirectional friendship
        conn.execute(
            "INSERT OR IGNORE INTO friendship (user_id, friend_id) VALUES (?, ?)",
            (req["from_user_id"], req["to_user_id"]),
        )
        conn.execute(
            "INSERT OR IGNORE INTO friendship (user_id, friend_id) VALUES (?, ?)",
            (req["to_user_id"], req["from_user_id"]),
        )
        conn.commit()

    return jsonify({"detail": "已接受"}), 200


@friend_bp.route("/deny/<int:request_id>", methods=["POST"])
@require_auth
def deny_request(request_id):
    with db_connection() as conn:
        req = conn.execute(
            "SELECT id, to_user_id, status FROM friend_request WHERE id=?",
            (request_id,),
        ).fetchone()
        if not req:
            return jsonify({"error": "请求不存在"}), 404
        if req["to_user_id"] != g.user_id:
            return jsonify({"error": "无权操作"}), 403

        conn.execute(
            "UPDATE friend_request SET status='denied' WHERE id=?", (request_id,)
        )
        conn.commit()
    return jsonify({"detail": "已拒绝"}), 200


@friend_bp.route("", methods=["GET"])
@require_auth
def list_friends():
    with db_connection() as conn:
        rows = conn.execute(
            "SELECT f.id, f.friend_id, u.display_name, u.email, f.share_usage, f.share_schedule "
            "FROM friendship f JOIN user u ON f.friend_id = u.id "
            "WHERE f.user_id = ? ORDER BY u.display_name",
            (g.user_id,),
        ).fetchall()

    friends = [
        {
            "id": r["id"],
            "friend_id": r["friend_id"],
            "display_name": r["display_name"],
            "email": r["email"],
            "share_usage": bool(r["share_usage"]),
            "share_schedule": bool(r["share_schedule"]),
        }
        for r in rows
    ]
    return jsonify({"friends": friends}), 200


@friend_bp.route("/remove/<int:friend_id>", methods=["DELETE"])
@require_auth
def remove_friend(friend_id):
    with db_connection() as conn:
        conn.execute(
            "DELETE FROM friendship WHERE user_id=? AND friend_id=?",
            (g.user_id, friend_id),
        )
        conn.execute(
            "DELETE FROM friendship WHERE user_id=? AND friend_id=?",
            (friend_id, g.user_id),
        )
        conn.commit()
    return jsonify({"detail": "已删除"}), 200


@friend_bp.route("/share/<int:friend_id>", methods=["PUT"])
@require_auth
def update_share(friend_id):
    body = request.get_json(silent=True) or {}
    try:
        data = FriendShareUpdate(**body)
    except Exception as e:
        return jsonify({"error": str(e)}), 422

    updates = []
    params = []
    if data.share_usage is not None:
        updates.append("share_usage = ?")
        params.append(1 if data.share_usage else 0)
    if data.share_schedule is not None:
        updates.append("share_schedule = ?")
        params.append(1 if data.share_schedule else 0)

    if not updates:
        return jsonify({"error": "无需更新"}), 400

    params.extend([g.user_id, friend_id])

    with db_connection() as conn:
        conn.execute(
            f"UPDATE friendship SET {', '.join(updates)}, updated_at = datetime('now') "
            "WHERE user_id=? AND friend_id=?",
            params,
        )
        conn.commit()

    return jsonify({"detail": "已更新"}), 200


@friend_bp.route("/<int:friend_id>/timeline", methods=["GET"])
@require_auth
def friend_timeline(friend_id):
    target_date = request.args.get("date", date.today().isoformat())

    with db_connection() as conn:
        # Verify friendship + share_usage permission
        friendship = conn.execute(
            "SELECT share_usage FROM friendship WHERE user_id=? AND friend_id=?",
            (friend_id, g.user_id),
        ).fetchone()
        if not friendship or not friendship["share_usage"]:
            return jsonify({"error": "无权限"}), 403

        devices = conn.execute(
            "SELECT id, name, platform FROM device WHERE user_id = ?",
            (friend_id,),
        ).fetchall()

        result_devices = []
        for dev in devices:
            events = conn.execute(
                "SELECT id, device_id, timestamp, app_name, category "
                "FROM timeline_event WHERE user_id=? AND device_id=? AND date(timestamp)=? "
                "ORDER BY timestamp ASC",
                (friend_id, dev["id"], target_date),
            ).fetchall()

            from protocol_models import TimelineEventResponse
            event_list = [
                TimelineEventResponse(
                    id=e["id"],
                    device_id=e["device_id"],
                    timestamp=datetime.fromisoformat(e["timestamp"]),
                    app_name=e["app_name"],
                    category=e["category"],
                ).model_dump()
                for e in events
            ]

            result_devices.append({
                "device_id": dev["id"],
                "device_name": dev["name"],
                "platform": dev["platform"],
                "event_count": len(event_list),
                "events": event_list,
            })

    return jsonify({
        "user_id": friend_id,
        "date": target_date,
        "devices": result_devices,
    }), 200


@friend_bp.route("/<int:friend_id>/schedule", methods=["GET"])
@require_auth
def friend_schedule(friend_id):
    with db_connection() as conn:
        friendship = conn.execute(
            "SELECT share_schedule FROM friendship WHERE user_id=? AND friend_id=?",
            (friend_id, g.user_id),
        ).fetchone()
        if not friendship or not friendship["share_schedule"]:
            return jsonify({"error": "无权限"}), 403

        row = conn.execute(
            "SELECT * FROM schedule WHERE user_id=? ORDER BY generated_at DESC LIMIT 1",
            (friend_id,),
        ).fetchone()

    if not row:
        return jsonify({"error": "暂无计划"}), 404

    return jsonify({
        "id": row["id"],
        "user_id": row["user_id"],
        "date": row["date"],
        "plan_markdown": row["plan_markdown"],
        "generated_at": row["generated_at"],
    }), 200
