"""
activity_tracker.py
Tracks the foreground window on Windows using Win32 API.
"""
import json
import sys
import time
from datetime import date, datetime
from pathlib import Path
from typing import Optional


PROCESS_DISPLAY_MAP = {
    "chrome.exe": "Google Chrome",
    "firefox.exe": "Firefox",
    "msedge.exe": "Edge",
    "code.exe": "Visual Studio Code",
    "devenv.exe": "Microsoft Visual Studio",
    "pycharm64.exe": "PyCharm",
    "pycharm.exe": "PyCharm",
    "idea64.exe": "IntelliJ IDEA",
    "idea.exe": "IntelliJ IDEA",
    "winword.exe": "Word",
    "excel.exe": "Excel",
    "powerpnt.exe": "PowerPoint",
    "outlook.exe": "Outlook",
    "windowsterminal.exe": "Windows Terminal",
    "wt.exe": "Windows Terminal",
    "powershell.exe": "PowerShell",
    "pwsh.exe": "PowerShell",
    "obsidian.exe": "Obsidian",
    "notion.exe": "Notion",
    "anki.exe": "Anki",
    "matlab.exe": "Matlab",
    "rstudio.exe": "RStudio",
    "zotero.exe": "Zotero",
    "mendeleydesktop.exe": "Mendeley",
    "steam.exe": "Steam",
    "vlc.exe": "VLC",
    "spotify.exe": "Spotify",
    "minecraft.exe": "Minecraft",
    "javaw.exe": "Minecraft",
    "wechat.exe": "WeChat",
    "qq.exe": "QQ",
    "discord.exe": "Discord",
    "telegram.exe": "Telegram",
    "bilibili.exe": "bilibili",
    "kindle.exe": "Kindle",
}


def get_project_root() -> Path:
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


def get_config() -> dict:
    config_path = get_project_root() / "config.json"
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def get_current_app_name() -> str:
    """Get the title of the current foreground window via Win32 API."""
    try:
        import win32gui
        hwnd = win32gui.GetForegroundWindow()
        title = win32gui.GetWindowText(hwnd)
        return title if title else "Desktop"
    except ImportError:
        print("[tracker] pywin32 not installed. Run: pip install pywin32", file=sys.stderr)
        return "Unknown"
    except Exception as e:
        print(f"[tracker] Failed to get window: {e}", file=sys.stderr)
        return "Unknown"


def get_process_name() -> str:
    """Get the process name of the foreground window."""
    try:
        import win32gui, win32process, psutil
        hwnd = win32gui.GetForegroundWindow()
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        return psutil.Process(pid).name()
    except Exception:
        return get_current_app_name()


def classify_app(app_name: str, config: Optional[dict] = None) -> str:
    """Classify an app name into 'learning', 'entertainment', or 'other'.
    Matches against both the raw process name and its mapped display name."""
    if config is None:
        config = get_config()

    tracker_cfg = config.get("tracker", {})
    learning_apps = tracker_cfg.get("learning_apps", [])
    entertainment_apps = tracker_cfg.get("entertainment_apps", [])

    app_lower = app_name.lower()
    display_name = PROCESS_DISPLAY_MAP.get(app_name, PROCESS_DISPLAY_MAP.get(app_lower, ""))
    display_lower = display_name.lower()

    def _matches(app_str: str, candidates: list[str]) -> bool:
        for c in candidates:
            c_lower = c.lower()
            if c_lower in app_str or c_lower in display_lower:
                return True
        return False

    if _matches(app_lower, learning_apps):
        return "learning"
    if _matches(app_lower, entertainment_apps):
        return "entertainment"
    return "other"


def get_activity_log_path(target_date: Optional[date] = None) -> Path:
    config = get_config()
    data_dir = get_project_root() / config.get("paths", {}).get("data_dir", "data")
    data_dir.mkdir(parents=True, exist_ok=True)
    if target_date is None:
        target_date = date.today()
    return data_dir / f"activity_log_{target_date.isoformat()}.json"


def record_current_app(target_date: Optional[date] = None) -> dict:
    if target_date is None:
        target_date = date.today()

    log_path = get_activity_log_path(target_date)
    now = datetime.now()
    window_title = get_current_app_name()
    process = get_process_name()

    # Use process name for classification (more reliable than window title)
    category = classify_app(process)

    entry = {
        "timestamp": now.isoformat(),
        "time": now.strftime("%H:%M:%S"),
        "app": process,
        "title": window_title,
        "category": category,
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
    Infinite loop: record foreground window at configured intervals.
    Optional callback is called with each entry.
    """
    config = get_config()
    interval_minutes = config.get("tracker", {}).get("record_interval_minutes", 20)
    interval_seconds = max(interval_minutes * 60, 30)

    print(f"[tracker] Started, interval={interval_minutes}min")

    try:
        while True:
            try:
                entry = record_current_app()
                print(f"[{entry['time']}] {entry['app']} ({entry['category']})")
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
