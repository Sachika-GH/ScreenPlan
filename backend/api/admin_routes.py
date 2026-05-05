"""Admin API — privileged endpoints for bot / automation access.

Protected by SCREENPLAN_ADMIN_TOKEN (Bearer token in Authorization header).
"""
from collections import defaultdict
from datetime import date, datetime
from functools import wraps

from flask import Blueprint, request, jsonify, g

from config import ADMIN_TOKEN, VERSION
from database import db_connection, get_uptime

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")

RECORD_INTERVAL_MIN = 3  # each timeline event = ~3 min of activity


def require_admin(f):
    """Decorator: reject unless Bearer token matches ADMIN_TOKEN."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not ADMIN_TOKEN:
            return jsonify({"error": "ADMIN_TOKEN not configured on server"}), 503
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid Authorization header"}), 401
        token = auth.split(" ", 1)[1]
        if token != ADMIN_TOKEN:
            return jsonify({"error": "Invalid admin token"}), 403
        return f(*args, **kwargs)
    return wrapper


# ─── health ──────────────────────────────────────────────

@admin_bp.route("/health", methods=["GET"])
@require_admin
def admin_health():
    with db_connection() as conn:
        user_count = conn.execute("SELECT COUNT(*) as cnt FROM user").fetchone()["cnt"]
        device_count = conn.execute("SELECT COUNT(*) as cnt FROM device").fetchone()["cnt"]
        today = date.today().isoformat()
        today_events = conn.execute(
            "SELECT COUNT(*) as cnt FROM timeline_event WHERE date(timestamp) = ?",
            (today,),
        ).fetchone()["cnt"]

    return jsonify({
        "status": "ok",
        "version": VERSION,
        "uptime_seconds": round(get_uptime(), 1),
        "user_count": user_count,
        "device_count": device_count,
        "today_events": today_events,
    }), 200


# ─── list users ──────────────────────────────────────────

@admin_bp.route("/users", methods=["GET"])
@require_admin
def list_users():
    with db_connection() as conn:
        rows = conn.execute(
            "SELECT id, email, display_name, created_at FROM user ORDER BY id"
        ).fetchall()

    users = [
        {
            "id": r["id"],
            "email": r["email"],
            "display_name": r["display_name"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]
    return jsonify({"users": users, "count": len(users)}), 200


# ─── user usage summary ──────────────────────────────────

@admin_bp.route("/usage/<int:user_id>", methods=["GET"])
@require_admin
def user_usage(user_id):
    target_date = request.args.get("date", date.today().isoformat())

    with db_connection() as conn:
        user = conn.execute(
            "SELECT id, email, display_name FROM user WHERE id = ?", (user_id,)
        ).fetchone()
        if not user:
            return jsonify({"error": "User not found"}), 404

        devices = conn.execute(
            "SELECT id, name, platform FROM device WHERE user_id = ?", (user_id,)
        ).fetchall()

        if not devices:
            return jsonify({
                "user_id": user_id,
                "display_name": user["display_name"],
                "email": user["email"],
                "date": target_date,
                "total_minutes_all_devices": 0.0,
                "overlap_minutes": 0.0,
                "devices": [],
            }), 200

        device_ids = [dev["id"] for dev in devices]
        placeholders = ",".join("?" for _ in device_ids)
        all_rows = conn.execute(
            f"SELECT te.device_id, te.app_name, te.category, te.timestamp "
            f"FROM timeline_event te "
            f"WHERE te.user_id = ? AND date(te.timestamp) = ? AND te.device_id IN ({placeholders}) "
            f"ORDER BY te.timestamp ASC",
            [user_id, target_date] + device_ids,
        ).fetchall()

        # Per-device breakdown
        dev_rows_map = defaultdict(list)
        all_timestamps = []
        for r in all_rows:
            dev_rows_map[r["device_id"]].append(r)
            all_timestamps.append(datetime.fromisoformat(r["timestamp"]))

        device_summaries = []
        for dev in devices:
            records = dev_rows_map.get(dev["id"], [])
            if not records:
                continue

            app_map = defaultdict(lambda: {"category": "", "duration_minutes": 0.0, "record_count": 0})
            for r in records:
                key = r["app_name"]
                app_map[key]["category"] = r["category"]
                app_map[key]["duration_minutes"] += RECORD_INTERVAL_MIN
                app_map[key]["record_count"] += 1

            total_mins = sum(v["duration_minutes"] for v in app_map.values())
            learning_mins = sum(v["duration_minutes"] for k, v in app_map.items() if v["category"] == "learning")
            entertainment_mins = sum(v["duration_minutes"] for k, v in app_map.items() if v["category"] == "entertainment")
            other_mins = sum(v["duration_minutes"] for k, v in app_map.items() if v["category"] == "other")

            denom = max(total_mins, 1)
            learning_pct = round(learning_mins / denom * 100, 1)
            entertainment_pct = round(entertainment_mins / denom * 100, 1)
            other_pct = round(other_mins / denom * 100, 1)

            sorted_apps = sorted(app_map.items(), key=lambda x: x[1]["duration_minutes"], reverse=True)[:10]
            top_apps = [
                {"app_name": name, "category": info["category"],
                 "total_minutes": round(info["duration_minutes"], 1),
                 "record_count": info["record_count"]}
                for name, info in sorted_apps
            ]

            device_summaries.append({
                "device_id": dev["id"],
                "device_name": dev["name"],
                "platform": dev["platform"],
                "total_minutes": round(total_mins, 1),
                "learning_pct": learning_pct,
                "entertainment_pct": entertainment_pct,
                "other_pct": other_pct,
                "top_apps": top_apps,
            })

        # Compute union duration (overlap)
        union_total = 0.0
        if len(all_timestamps) >= 2:
            sorted_ts = sorted(all_timestamps)
            intervals = [(ts.timestamp(), ts.timestamp() + RECORD_INTERVAL_MIN * 60) for ts in sorted_ts]
            intervals.sort()
            merged_start, merged_end = intervals[0]
            for s, e in intervals[1:]:
                if s <= merged_end:
                    merged_end = max(merged_end, e)
                else:
                    union_total += (merged_end - merged_start) / 60
                    merged_start, merged_end = s, e
            union_total += (merged_end - merged_start) / 60
        elif all_timestamps:
            union_total = RECORD_INTERVAL_MIN

        # Compute sum of all device totals for overlap calculation
        sum_total = sum(ds["total_minutes"] for ds in device_summaries)
        overlap = round(max(sum_total - union_total, 0.0), 1)

    return jsonify({
        "user_id": user_id,
        "display_name": user["display_name"],
        "email": user["email"],
        "date": target_date,
        "total_minutes_all_devices": round(union_total, 1),
        "overlap_minutes": overlap,
        "devices": device_summaries,
    }), 200


# ─── user full timeline ──────────────────────────────────

@admin_bp.route("/timeline/<int:user_id>", methods=["GET"])
@require_admin
def user_timeline(user_id):
    target_date = request.args.get("date", date.today().isoformat())

    with db_connection() as conn:
        user = conn.execute(
            "SELECT id, email, display_name FROM user WHERE id = ?", (user_id,)
        ).fetchone()
        if not user:
            return jsonify({"error": "User not found"}), 404

        devices = conn.execute(
            "SELECT id, name, platform FROM device WHERE user_id = ?", (user_id,)
        ).fetchall()

        device_summaries = []
        for dev in devices:
            rows = conn.execute(
                "SELECT id, device_id, timestamp, app_name, category "
                "FROM timeline_event "
                "WHERE user_id = ? AND device_id = ? AND date(timestamp) = ? "
                "ORDER BY timestamp ASC",
                (user_id, dev["id"], target_date),
            ).fetchall()

            events = [
                {
                    "id": r["id"],
                    "device_id": r["device_id"],
                    "timestamp": r["timestamp"],
                    "app_name": r["app_name"],
                    "category": r["category"],
                }
                for r in rows
            ]

            device_summaries.append({
                "device_id": dev["id"],
                "device_name": dev["name"],
                "platform": dev["platform"],
                "event_count": len(events),
                "events": events,
            })

    return jsonify({
        "user_id": user_id,
        "display_name": user["display_name"],
        "email": user["email"],
        "date": target_date,
        "devices": device_summaries,
    }), 200
