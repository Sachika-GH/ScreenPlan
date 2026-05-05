"""Schedule generation and retrieval routes."""
from datetime import date, datetime, timedelta
from collections import defaultdict

from flask import Blueprint, request, jsonify, g

from database import db_connection
from protocol_models import ScheduleGenerateRequest, ScheduleResponse
from schedule_engine import (
    SYSTEM_PROMPT,
    build_multi_day_usage_context,
    build_user_prompt,
    compute_union_duration,
)
from llm_client import generate_plan
from api.device_routes import require_auth

schedule_bp = Blueprint("schedule", __name__, url_prefix="/api/schedule")


def _get_usage_summary_for_user(user_id: int, target_date: date):
    """Internal helper to get usage summary for schedule generation.
    Returns (device_summaries: list[dict], union_total: float)."""
    RECORD_INTERVAL_MIN = 3
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
    is_workday = target_date.weekday() < 5

    # Fetch usage data from past 3 days (yesterday excluded because it may be incomplete,
    # we analyze the 3 days before yesterday for trend analysis, plus yesterday for latest)
    # Actually: fetch past several days up to yesterday
    LOOKBACK_DAYS = 3
    multi_day_data = {}
    for offset in range(1, LOOKBACK_DAYS + 1):
        check_date = target_date - timedelta(days=offset)
        devices_usage, union_total = _get_usage_summary_for_user(g.user_id, check_date)
        if devices_usage:
            multi_day_data[check_date.isoformat()] = (devices_usage, union_total)

    usage_context = build_multi_day_usage_context(multi_day_data)

    # If no data at all, provide a default message
    if not usage_context or usage_context == "（暂无使用数据）":
        usage_context = "（暂无使用数据——请先确保您的设备已上报至少一天的使用记录）"

    # Build prompt
    user_prompt = build_user_prompt(
        usage_context=usage_context,
        calendar_text="",
        is_workday=is_workday,
        learning_hours_goal=4 if is_workday else 2,
    )

    # Get user's API key from DB (per-user key takes priority over server-level)
    user_api_key = None
    with db_connection() as conn:
        user = conn.execute(
            "SELECT llm_api_key FROM user WHERE id = ?",
            (g.user_id,),
        ).fetchone()
        if user and user["llm_api_key"]:
            user_api_key = user["llm_api_key"]

    # Call LLM
    plan_text = generate_plan(SYSTEM_PROMPT, user_prompt, api_key=user_api_key)
    if not plan_text:
        if not user_api_key:
            return jsonify({"error": "请先在 Web UI 的「日程建议」页面配置您的 DeepSeek API Key"}), 402
        return jsonify({"error": "LLM 调用失败，请检查您的 API Key 是否正确"}), 502

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
        return jsonify({"error": "暂无分析报告"}), 404

    resp = ScheduleResponse(
        id=row["id"],
        user_id=row["user_id"],
        date=date.fromisoformat(row["date"]),
        plan_markdown=row["plan_markdown"],
        generated_at=row["generated_at"],
    )
    return jsonify(resp.model_dump()), 200
