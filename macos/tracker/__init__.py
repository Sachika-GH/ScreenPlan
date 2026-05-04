"""
activity_tracker.py
Records the current foreground application on macOS.
Uses AppleScript to get the frontmost application name.
"""
import json
import os
import subprocess
import sys
import time
from datetime import date, datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

try:
    import Quartz
    _HAS_QUARTZ = True
except ImportError:
    _HAS_QUARTZ = False


def get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def get_config() -> dict:
    config_path = get_project_root() / "config.json"
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def get_current_app_name() -> str:
    """Get the name of the current foreground application via AppleScript."""
    script = 'tell application "System Events" to get name of first application process whose frontmost is true'
    try:
        proc = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout.strip()
    except Exception as e:
        print(f"[tracker] Failed to get app: {e}", file=sys.stderr)
    return "Unknown"


def get_idle_seconds() -> float:
    """Return seconds since last user input (keyboard/mouse).
    Returns -1 if Quartz framework is unavailable."""
    if not _HAS_QUARTZ:
        return -1
    try:
        return Quartz.CGEventSourceSecondsSinceLastEventType(
            Quartz.kCGEventSourceStateHIDSystemState,
            Quartz.kCGAnyInputEventType,
        )
    except Exception:
        return -1


def get_browser_tab_info(app_name: str) -> Optional[dict]:
    """Get active tab URL and title for a browser app via AppleScript.
    Returns {"url": str, "title": str} or None on failure."""
    browser_scripts = {
        "Google Chrome": (
            'tell application "Google Chrome"'
            ' to get {URL, title} of active tab of front window'
        ),
        "Safari": (
            'tell application "Safari"'
            ' to get {URL, name} of current tab of front window'
        ),
        "Firefox": (
            'tell application "Firefox"'
            ' to get {URL, name} of active tab of front window'
        ),
    }
    script = browser_scripts.get(app_name)
    if not script:
        return None

    try:
        proc = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=10,
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            return None
        parts = [p.strip() for p in proc.stdout.strip().split(",", 1)]
        if len(parts) != 2:
            return None
        return {"url": parts[0], "title": parts[1]}
    except Exception:
        return None


def classify_url(url: str, config: Optional[dict] = None) -> Optional[str]:
    """Classify a URL into 'entertainment' based on domain rules.
    Returns None if no rule matches (fall back to app-level classification)."""
    if config is None:
        config = get_config()

    url_rules = config.get("url_rules", {})
    entertainment_domains = url_rules.get("entertainment_domains", [])

    if not entertainment_domains or not url:
        return None

    try:
        parsed = urlparse(url)
        hostname = parsed.hostname or ""
    except Exception:
        return None

    hostname_lower = hostname.lower()

    for domain in entertainment_domains:
        domain_lower = domain.lower()
        if hostname_lower == domain_lower or hostname_lower.endswith("." + domain_lower):
            return "entertainment"

    return None


def classify_app(app_name: str, config: Optional[dict] = None) -> str:
    """Classify an app name into 'learning', 'entertainment', or 'other'."""
    if config is None:
        config = get_config()

    tracker_cfg = config.get("tracker", {})
    learning_apps = tracker_cfg.get("learning_apps", [])
    entertainment_apps = tracker_cfg.get("entertainment_apps", [])

    app_lower = app_name.lower()

    for la in learning_apps:
        if la.lower() == app_lower:
            return "learning"
    for ea in entertainment_apps:
        if ea.lower() == app_lower:
            return "entertainment"
    return "other"


def get_activity_log_path(target_date: Optional[date] = None) -> Path:
    """Get the file path for the daily activity log."""
    config = get_config()
    data_dir = get_project_root() / config.get("paths", {}).get("data_dir", "data")
    data_dir.mkdir(parents=True, exist_ok=True)

    if target_date is None:
        target_date = date.today()
    return data_dir / f"activity_log_{target_date.isoformat()}.json"


def record_current_app(target_date: Optional[date] = None) -> Optional[dict]:
    """Record the current foreground app and return the entry.
    Returns None if the system is idle (no user input) beyond the configured threshold.
    For browsers, also captures the active tab URL/title and classifies based on domain."""
    if target_date is None:
        target_date = date.today()

    config = get_config()
    idle_threshold_minutes = config.get("tracker", {}).get("idle_threshold_minutes", 2)
    idle_seconds = get_idle_seconds()
    if idle_seconds > idle_threshold_minutes * 60:
        print(f"[tracker] Skipping record: idle for {idle_seconds:.0f}s (threshold={idle_threshold_minutes}min)",
              file=sys.stderr)
        return None

    log_path = get_activity_log_path(target_date)
    now = datetime.now()
    app_name = get_current_app_name()
    category = classify_app(app_name)

    url = None
    title = None
    tab_info = get_browser_tab_info(app_name)
    if tab_info is not None:
        url = tab_info.get("url")
        title = tab_info.get("title")
        url_category = classify_url(url, config)
        if url_category is not None:
            category = url_category
            if url_category == "entertainment":
                print(f"[tracker] URL override: {url} → entertainment", file=sys.stderr)

    entry = {
        "timestamp": now.isoformat(),
        "time": now.strftime("%H:%M:%S"),
        "app": app_name,
        "category": category,
        "url": url,
        "title": title,
    }

    records = []
    if log_path.exists():
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                records = json.load(f)
        except (json.JSONDecodeError, IOError):
            records = []

    records.append(entry)

    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    return entry


def read_activity_log(target_date: Optional[date] = None) -> list[dict]:
    """Read the activity log for a given date."""
    log_path = get_activity_log_path(target_date)
    if not log_path.exists():
        return []
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def run_tracker_loop(record_callback=None):
    """
    Infinite loop: record current app at configured intervals.
    Optional callback is called with each entry.
    Detects macOS sleep via clock drift and skips recording during idle periods.
    """
    config = get_config()
    interval_minutes = config.get("tracker", {}).get("record_interval_minutes", 20)
    interval_seconds = max(interval_minutes * 60, 30)

    print(f"[tracker] Started, interval={interval_minutes}min")

    t0 = time.monotonic()

    try:
        while True:
            t1 = time.monotonic()
            elapsed = t1 - t0
            drift = elapsed - interval_seconds

            if drift > interval_seconds * 2:
                print(f"[tracker] Sleep/wake detected (drift={drift:.0f}s)",
                      file=sys.stderr)

            t0 = time.monotonic()

            try:
                entry = record_current_app()
                if entry is not None:
                    url_info = ""
                    if entry.get("url"):
                        url_info = f" | {entry['url']}"
                    print(f"[{entry['time']}] {entry['app']} ({entry['category']}){url_info}")
                    if record_callback:
                        try:
                            record_callback(entry)
                        except Exception as e:
                            print(f"[tracker] Callback error: {e}", file=sys.stderr)
            except Exception as e:
                print(f"[tracker] Record error: {e}, retrying...", file=sys.stderr)

            time.sleep(interval_seconds)
    except KeyboardInterrupt:
        print("\n[tracker] Stopped")
