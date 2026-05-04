"""Schedule generation and retrieval routes."""
from datetime import date, datetime

from flask import Blueprint, request, jsonify, g

from database import db_connection
from protocol_models import ScheduleGenerateRequest, ScheduleResponse
from schedule_engine import SYSTEM_PROMPT, build_usage_context, build_user_prompt, compute_union_duration
from llm_client import generate_plan
from api.device_routes import require_auth

schedule_bp = Blueprint("schedule", __name__, url_prefix="/api/schedule")


def _get_usage_summary_for_user(user_id: int, target_date: date):
    """Internal helper to get usage summary for schedule generation.
    Returns (device_summaries: list[dict], union_total: float)."""
    RECORD_INTERVAL_MIN = 3
    from collections import defaultdict
    with db_connection() as conn:
        devices = conn.execute(
            "SELECT id, name, platform FROM device WHERE user_id = ?",
            (user_id,),
        ).fetchall()

        if not devices:
            return [], 0.0

        # Bulk fetch all timeline events
        device_ids = [dev["id"] for dev in devices]
        placeholders = ",".join("?" for _ in device_ids)
        all_rows = conn.execute(
            f"SELECT te.device_id, te.app_name, te.category, te.timestamp "
            f"FROM timeline_event te "
            f"WHERE te.user_id = ? AND date(te.timestamp) = ? AND te.device_id IN ({placeholders}) "
            f"ORDER BY te.timestamp ASC",
            [user_id, target_date.isoformat()] + device_ids,
        ).fetchall()

        # Union total
        all_timestamps = [datetime.fromisoformat(r["timestamp"]) for r in all_rows]
        union_total, _ = compute_union_duration(all_timestamps, RECORD_INTERVAL_MIN)

        # Per-device breakdowns
        device_summaries = []
        from collections import defaultdict as dd
        dev_rows_map = dd(list)
        for r in all_rows:
            dev_rows_map[r["device_id"]].append(r)

        for dev in devices:
            records = dev_rows_map.get(dev["id"], [])
            if not records:
                continue

            app_map = defaultdict(lambda: {"total_minutes": 0.0, "category": ""})
            for r in records:
                app_map[r["app_name"]]["total_minutes"] += RECORD_INTERVAL_MIN
                app_map[r["app_name"]]["category"] = r["category"]

            total_mins = sum(v["total_minutes"] for v in app_map.values())
            learning_mins = sum(v["total_minutes"] for k, v in app_map.items() if v["category"] == "learning")
            entertainment_mins = sum(v["total_minutes"] for k, v in app_map.items() if v["category"] == "entertainment")
            other_mins = sum(v["total_minutes"] for k, v in app_map.items() if v["category"] == "other")
            denom = max(total_mins, 1)

            top_apps = sorted(app_map.items(), key=lambda x: x[1]["total_minutes"], reverse=True)[:5]
            top_apps_list = [
                {"app_name": name, "total_minutes": round(info["total_minutes"], 1), "category": info["category"]}
                for name, info in top_apps
            ]

            device_summaries.append({
                "device_id": dev["id"],
                "device_name": dev["name"],
                "platform": dev["platform"],
                "total_minutes": round(total_mins, 1),
                "learning_pct": round(learning_mins / denom * 100, 1),
                "entertainment_pct": round(entertainment_mins / denom * 100, 1),
                "other_pct": round(other_mins / denom * 100, 1),
                "top_apps": top_apps_list,
            })

    return device_summaries, union_total


@schedule_bp.route("/generate", methods=["POST"])
@require_auth
def generate():
    body = request.get_json(silent=True) or {}
    try:
        data = ScheduleGenerateRequest(**body)
    except Exception as e:
        return jsonify({"error": str(e)}), 422

    target_date = data.date or date.today()

    # Determine workday
    is_workday = target_date.weekday() < 5

    # Get yesterday's usage across all devices
    from datetime import timedelta
    yesterday = target_date - timedelta(days=1)
    devices_usage, union_total = _get_usage_summary_for_user(g.user_id, yesterday)
    usage_context = build_usage_context(devices_usage, union_total)

    # Build prompt
    calendar_text = ""  # Calendar data comes from macOS agent in future phase
    user_prompt = build_user_prompt(
        usage_context=usage_context,
        calendar_text=calendar_text,
        is_workday=is_workday,
        learning_hours_goal=4 if is_workday else 2,
    )

    # Call LLM
    plan_text = generate_plan(SYSTEM_PROMPT, user_prompt)
    if not plan_text:
        return jsonify({"error": "LLM 调用失败，请检查 API Key 配置"}), 502

    # Save to DB
    with db_connection() as conn:
        cur = conn.execute(
            "INSERT INTO schedule (user_id, date, plan_markdown) VALUES (?, ?, ?)",
            (g.user_id, target_date.isoformat(), plan_text),
        )
        conn.commit()
        schedule_id = cur.lastrowid
        row = conn.execute("SELECT * FROM schedule WHERE id = ?", (schedule_id,)).fetchone()

    resp = ScheduleResponse(
        id=row["id"],
        user_id=row["user_id"],
        date=date.fromisoformat(row["date"]),
        plan_markdown=row["plan_markdown"],
        generated_at=row["generated_at"],
    )
    return jsonify(resp.model_dump()), 200


@schedule_bp.route("/latest", methods=["GET"])
@require_auth
def latest():
    with db_connection() as conn:
        row = conn.execute(
            "SELECT * FROM schedule WHERE user_id = ? ORDER BY generated_at DESC LIMIT 1",
            (g.user_id,),
        ).fetchone()

    if not row:
        return jsonify({"error": "暂无生成的计划"}), 404

    resp = ScheduleResponse(
        id=row["id"],
        user_id=row["user_id"],
        date=date.fromisoformat(row["date"]),
        plan_markdown=row["plan_markdown"],
        generated_at=row["generated_at"],
    )
    return jsonify(resp.model_dump()), 200
