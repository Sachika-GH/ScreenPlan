"""
analyzer.py
Analyzes activity logs and computes usage statistics.
"""
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from tracker import classify_app


def get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def analyze_activity(records: list[dict], config: Optional[dict] = None) -> dict[str, Any]:
    if config is None:
        config_path = get_project_root() / "config.json"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
        else:
            config = {}

    if not records:
        return {
            "total_records": 0,
            "total_time_hours": 0,
            "learning_time_pct": 0,
            "entertainment_time_pct": 0,
            "switch_count": 0,
            "longest_focus_minutes": 0,
            "focus_sessions": [],
            "app_breakdown": {},
            "classification": "无数据",
        }

    tracker_cfg = config.get("tracker", {})
    analyzer_cfg = config.get("analyzer", {})
    record_interval = tracker_cfg.get("record_interval_minutes", 20)
    max_gap = analyzer_cfg.get("max_switch_gap_minutes", record_interval * 2)

    # Parse timestamps and compute per-record durations (capped at max_gap)
    prev_ts: Optional[datetime] = None
    durations: list[dict] = []
    for rec in records:
        app = rec.get("app", "Unknown")
        cat = rec.get("category") or classify_app(app, config)
        try:
            ts = datetime.fromisoformat(rec["timestamp"])
        except (KeyError, ValueError):
            ts = datetime.now()

        if prev_ts is not None:
            delta_minutes = (ts - prev_ts).total_seconds() / 60.0
            capped = min(delta_minutes, record_interval)
            durations.append({
                "app": app,
                "category": cat,
                "minutes": capped,
                "gap_minutes": delta_minutes,
            })
        prev_ts = ts

    if not durations:
        return {
            "total_records": len(records),
            "total_time_hours": 0,
            "learning_time_pct": 0,
            "entertainment_time_pct": 0,
            "switch_count": 0,
            "longest_focus_minutes": 0,
            "focus_sessions": [],
            "app_breakdown": {},
            "classification": "无数据",
        }

    total_minutes = sum(d["minutes"] for d in durations)
    total_time_hours = total_minutes / 60.0

    learning_minutes = sum(d["minutes"] for d in durations if d["category"] == "learning")
    entertainment_minutes = sum(d["minutes"] for d in durations if d["category"] == "entertainment")
    other_minutes = total_minutes - learning_minutes - entertainment_minutes

    learning_pct = round(learning_minutes / max(total_minutes, 1) * 100, 1)
    entertainment_pct = round(entertainment_minutes / max(total_minutes, 1) * 100, 1)
    other_pct = round(other_minutes / max(total_minutes, 1) * 100, 1)

    app_counts: dict[str, int] = {}
    for d in durations:
        app_counts[d["app"]] = app_counts.get(d["app"], 0) + 1
    app_breakdown = dict(
        sorted(app_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    )

    switch_count = 0
    prev_app = durations[0]["app"] if durations else None
    for d in durations[1:]:
        if d["app"] != prev_app and d["gap_minutes"] <= max_gap:
            switch_count += 1
        prev_app = d["app"]

    longest_focus_minutes = 0.0
    current_streak = 0.0
    streak_app = None
    for d in durations:
        if d["app"] == streak_app and d["gap_minutes"] <= max_gap:
            current_streak += d["minutes"]
        else:
            if current_streak > longest_focus_minutes:
                longest_focus_minutes = current_streak
            current_streak = d["minutes"]
            streak_app = d["app"]
    if current_streak > longest_focus_minutes:
        longest_focus_minutes = current_streak

    if learning_pct >= 50:
        classification = "高度学习型"
    elif entertainment_pct >= 50:
        classification = "偏娱乐型"
    elif learning_pct >= 30:
        classification = "学习娱乐平衡型"
    elif entertainment_pct >= 30:
        classification = "轻度娱乐型"
    else:
        classification = "中性/其他型"

    return {
        "total_records": len(records),
        "total_time_hours": round(total_time_hours, 2),
        "learning_time_pct": learning_pct,
        "entertainment_time_pct": entertainment_pct,
        "other_time_pct": other_pct,
        "switch_count": switch_count,
        "longest_focus_minutes": round(longest_focus_minutes, 1),
        "focus_sessions": [],
        "app_breakdown": app_breakdown,
        "classification": classification,
    }


def is_workday(target_date: Optional[date] = None) -> bool:
    if target_date is None:
        target_date = date.today()
    return target_date.weekday() < 5


def aggregate_usage_for_upload(records: list[dict], config: Optional[dict] = None) -> list[dict]:
    """Convert raw activity records into summarized usage records for upload.
    Groups by (app_name, category), uses actual timestamp deltas (capped at interval),
    excludes Unknown records. URL/title fields are local-only — stripped from upload."""
    if config is None:
        config_path = get_project_root() / "config.json"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
        else:
            config = {}
    tracker_cfg = config.get("tracker", {})
    interval = tracker_cfg.get("record_interval_minutes", 20)

    app_map: dict[tuple, dict] = {}
    prev_ts: Optional[datetime] = None

    for rec in records:
        app = rec.get("app", "Unknown")
        if app == "Unknown":
            continue
        cat = rec.get("category") or classify_app(app, config)
        try:
            ts = datetime.fromisoformat(rec["timestamp"])
        except (KeyError, ValueError):
            ts = datetime.now()

        delta = 0.0
        if prev_ts is not None:
            delta = min((ts - prev_ts).total_seconds() / 60.0, interval)
        prev_ts = ts

        key = (app, cat)
        if key not in app_map:
            app_map[key] = {"app_name": app, "category": cat, "duration_minutes": 0.0, "records": 0}
        app_map[key]["duration_minutes"] += delta
        app_map[key]["records"] += 1

    return [
        {
            "app_name": v["app_name"],
            "category": v["category"],
            "duration_minutes": round(v["duration_minutes"], 1),
        }
        for v in app_map.values()
    ]
