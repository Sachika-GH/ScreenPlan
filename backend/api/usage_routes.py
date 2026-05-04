"""Usage data upload and summary routes."""
from collections import defaultdict
from datetime import date, datetime, timedelta

from flask import Blueprint, request, jsonify, g

from database import db_connection
from protocol_models import (
    UsageUploadRequest, UsageSummaryResponse, UsageSummaryPerDevice, UsageSummaryPerApp,
    TimelineUploadRequest, TimelineEventResponse, TimelineResponse,
    FullTimelineResponse, TimelineDeviceSummary,
)
from api.device_routes import require_auth
from schedule_engine import compute_union_duration

usage_bp = Blueprint("usage", __name__, url_prefix="/api/usage")


@usage_bp.route("/upload", methods=["POST"])
@require_auth
def upload():
    body = request.get_json(silent=True)
    if not body:
        return jsonify({"error": "Invalid JSON"}), 400

    try:
        data = UsageUploadRequest(**body)
    except Exception as e:
        return jsonify({"error": str(e)}), 422

    with db_connection() as conn:
        # Verify device belongs to user
        device = conn.execute(
            "SELECT id FROM device WHERE id = ? AND user_id = ?",
            (data.device_id, g.user_id),
        ).fetchone()
        if not device:
            return jsonify({"error": "设备不属于此用户"}), 403

        # Delete old records for this device+date (idempotent upload)
        conn.execute(
            "DELETE FROM usage_record WHERE device_id = ? AND date = ? AND user_id = ?",
            (data.device_id, data.date.isoformat(), g.user_id),
        )

        # Insert new records
        for rec in data.records:
            conn.execute(
                "INSERT INTO usage_record (device_id, user_id, date, app_name, category, duration_minutes) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    data.device_id,
                    g.user_id,
                    data.date.isoformat(),
                    rec.app_name,
                    rec.category.value,
                    rec.duration_minutes,
                ),
            )

        conn.commit()

    return jsonify({"detail": f"uploaded {len(data.records)} records"}), 201


@usage_bp.route("/summary", methods=["GET"])
@require_auth
def summary():
    target_date = request.args.get("date", date.today().isoformat())
    RECORD_INTERVAL_MIN = 3

    with db_connection() as conn:
        devices = conn.execute(
            "SELECT id, name, platform FROM device WHERE user_id = ?",
            (g.user_id,),
        ).fetchall()

        if not devices:
            return jsonify(UsageSummaryResponse(
                user_id=g.user_id,
                date=date.fromisoformat(target_date),
                total_minutes_all_devices=0.0,
                devices=[],
            ).model_dump()), 200

        # Fetch all timeline events for all user devices in one query
        device_ids = [dev["id"] for dev in devices]
        placeholders = ",".join("?" for _ in device_ids)
        all_rows = conn.execute(
            f"SELECT te.device_id, te.app_name, te.category, te.timestamp "
            f"FROM timeline_event te "
            f"WHERE te.user_id = ? AND date(te.timestamp) = ? AND te.device_id IN ({placeholders}) "
            f"ORDER BY te.timestamp ASC",
            [g.user_id, target_date] + device_ids,
        ).fetchall()

        # Collect all timestamps for union computation
        all_timestamps = [datetime.fromisoformat(r["timestamp"]) for r in all_rows]
        union_total, sum_total = compute_union_duration(all_timestamps, RECORD_INTERVAL_MIN)
        overlap_mins = round(max(sum_total - union_total, 0.0), 1)

        # Build per-device breakdowns
        device_summaries = []
        dev_rows_map = defaultdict(list)
        for r in all_rows:
            dev_rows_map[r["device_id"]].append(r)

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
            top_apps_list = [
                UsageSummaryPerApp(
                    app_name=name,
                    category=info["category"],
                    total_minutes=round(info["duration_minutes"], 1),
                    record_count=info["record_count"],
                )
                for name, info in sorted_apps
            ]

            switch_count = len(app_map)
            longest_focus = max((v["duration_minutes"] for v in app_map.values()), default=0.0)

            device_summaries.append(
                UsageSummaryPerDevice(
                    device_id=dev["id"],
                    device_name=dev["name"],
                    platform=dev["platform"],
                    total_minutes=round(total_mins, 1),
                    learning_pct=learning_pct,
                    entertainment_pct=entertainment_pct,
                    other_pct=other_pct,
                    switch_count=switch_count,
                    longest_focus_minutes=round(longest_focus, 1),
                    top_apps=top_apps_list,
                )
            )

    resp = UsageSummaryResponse(
        user_id=g.user_id,
        date=date.fromisoformat(target_date),
        total_minutes_all_devices=union_total,
        overlap_minutes=overlap_mins,
        devices=[d for d in device_summaries],
    )
    return jsonify(resp.model_dump()), 200


@usage_bp.route("/timeline/upload", methods=["POST"])
@require_auth
def upload_timeline():
    body = request.get_json(silent=True)
    if not body:
        return jsonify({"error": "Invalid JSON"}), 400

    try:
        data = TimelineUploadRequest(**body)
    except Exception as e:
        return jsonify({"error": str(e)}), 422

    with db_connection() as conn:
        device = conn.execute(
            "SELECT id FROM device WHERE id = ? AND user_id = ?",
            (data.device_id, g.user_id),
        ).fetchone()
        if not device:
            return jsonify({"error": "设备不属于此用户"}), 403

        for evt in data.events:
            conn.execute(
                "INSERT INTO timeline_event (device_id, user_id, timestamp, app_name, category) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    data.device_id,
                    g.user_id,
                    evt.timestamp.isoformat(),
                    evt.app_name,
                    evt.category.value,
                ),
            )
        conn.commit()

    return jsonify({"detail": f"uploaded {len(data.events)} events"}), 201


@usage_bp.route("/timeline", methods=["GET"])
@require_auth
def get_timeline():
    target_date = request.args.get("date", date.today().isoformat())
    device_id = request.args.get("device_id", None, type=int)

    with db_connection() as conn:
        if device_id:
            device = conn.execute(
                "SELECT id FROM device WHERE id = ? AND user_id = ?",
                (device_id, g.user_id),
            ).fetchone()
            if not device:
                return jsonify({"error": "设备不属于此用户"}), 403

        query = (
            "SELECT id, device_id, timestamp, app_name, category "
            "FROM timeline_event "
            "WHERE user_id = ? AND date(timestamp) = ?"
        )
        params = [g.user_id, target_date]

        if device_id:
            query += " AND device_id = ?"
            params.append(device_id)

        query += " ORDER BY timestamp ASC"

        rows = conn.execute(query, params).fetchall()

    events = [
        TimelineEventResponse(
            id=r["id"],
            device_id=r["device_id"],
            timestamp=datetime.fromisoformat(r["timestamp"]),
            app_name=r["app_name"],
            category=r["category"],
        )
        for r in rows
    ]

    resp = TimelineResponse(
        user_id=g.user_id,
        device_id=device_id,
        date=date.fromisoformat(target_date),
        events=events,
    )
    return jsonify(resp.model_dump()), 200


@usage_bp.route("/timeline/full", methods=["GET"])
@require_auth
def full_timeline():
    target_date = request.args.get("date", date.today().isoformat())

    with db_connection() as conn:
        devices = conn.execute(
            "SELECT id, name, platform FROM device WHERE user_id = ?",
            (g.user_id,),
        ).fetchall()

        device_summaries = []
        for dev in devices:
            rows = conn.execute(
                "SELECT id, device_id, timestamp, app_name, category "
                "FROM timeline_event "
                "WHERE user_id = ? AND device_id = ? AND date(timestamp) = ? "
                "ORDER BY timestamp ASC",
                (g.user_id, dev["id"], target_date),
            ).fetchall()

            events = [
                TimelineEventResponse(
                    id=r["id"],
                    device_id=r["device_id"],
                    timestamp=datetime.fromisoformat(r["timestamp"]),
                    app_name=r["app_name"],
                    category=r["category"],
                )
                for r in rows
            ]

            device_summaries.append(
                TimelineDeviceSummary(
                    device_id=dev["id"],
                    device_name=dev["name"],
                    platform=dev["platform"],
                    event_count=len(events),
                    events=events,
                )
            )

    resp = FullTimelineResponse(
        user_id=g.user_id,
        date=date.fromisoformat(target_date),
        devices=device_summaries,
    )
    return jsonify(resp.model_dump()), 200
