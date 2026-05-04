"""
sync_client.py - Syncs activity data to the ScreenPlan backend.
"""
import json
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import requests

from network.gateway import get_server_url
from protocol_models import TimelineEvent, TimelineUploadRequest, AuthResponse, HealthResponse

SYNC_TIMEOUT = 15
OFFLINE_QUEUE_FILE = (
    Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))) / "ScreenPlan" / "offline_queue.json"
    if getattr(sys, 'frozen', False)
    else Path(__file__).resolve().parent.parent / "data" / "offline_queue.json"
)


def get_backend_url() -> Optional[str]:
    return get_server_url()


def health_check() -> Optional[HealthResponse]:
    base = get_backend_url()
    if not base:
        return None
    try:
        resp = requests.get(f"{base}/api/health", timeout=5)
        resp.raise_for_status()
        return HealthResponse(**resp.json())
    except Exception:
        return None


def login(email: str, password: str) -> Optional[AuthResponse]:
    base = get_backend_url()
    if not base:
        return None
    try:
        resp = requests.post(
            f"{base}/api/auth/login",
            json={"email": email, "password": password},
            timeout=SYNC_TIMEOUT,
        )
        if resp.status_code == 200:
            return AuthResponse(**resp.json())
        else:
            print(f"[sync] Login failed: {resp.json().get('error', '?')}", file=sys.stderr)
            return None
    except Exception as e:
        print(f"[sync] Login error: {e}", file=sys.stderr)
        return None


def register(family_name: str, email: str, password: str, display_name: str) -> Optional[AuthResponse]:
    base = get_backend_url()
    if not base:
        return None
    try:
        resp = requests.post(
            f"{base}/api/auth/register",
            json={"family_name": family_name, "email": email, "password": password, "display_name": display_name},
            timeout=SYNC_TIMEOUT,
        )
        if resp.status_code == 201:
            return AuthResponse(**resp.json())
        else:
            print(f"[sync] Register failed: {resp.json().get('error', '?')}", file=sys.stderr)
            return None
    except Exception as e:
        print(f"[sync] Register error: {e}", file=sys.stderr)
        return None


def register_device(token: str, name: str, platform: str = "windows") -> Optional[int]:
    base = get_backend_url()
    if not base:
        return None
    try:
        resp = requests.post(
            f"{base}/api/devices",
            json={"name": name, "platform": platform},
            headers={"Authorization": f"Bearer {token}"},
            timeout=SYNC_TIMEOUT,
        )
        if resp.status_code in (200, 201):
            return resp.json()["id"]
        else:
            print(f"[sync] Device register failed: {resp.json()}", file=sys.stderr)
            return None
    except Exception as e:
        print(f"[sync] Device register error: {e}", file=sys.stderr)
        return None


def upload_timeline_event(token: str, device_id: int, entry: dict) -> bool:
    base = get_backend_url()
    if not base or not token:
        save_to_offline_queue(device_id, entry)
        return False

    try:
        ts = datetime.fromisoformat(entry["timestamp"])
    except (ValueError, KeyError):
        return False

    event = TimelineEvent(
        app_name=entry.get("app", "Unknown"),
        category=entry.get("category", "other"),
        timestamp=ts,
    )

    req = TimelineUploadRequest(device_id=device_id, events=[event])

    try:
        resp = requests.post(
            f"{base}/api/usage/timeline/upload",
            json=req.model_dump(mode="json"),
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
        )
        return resp.status_code == 201
    except Exception:
        save_to_offline_queue(device_id, entry)
        return False


def save_to_offline_queue(device_id: int, entry: dict) -> None:
    OFFLINE_QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
    queue = []
    if OFFLINE_QUEUE_FILE.exists():
        try:
            queue = json.loads(OFFLINE_QUEUE_FILE.read_text())
        except (json.JSONDecodeError, IOError):
            queue = []
    queue.append({
        "device_id": device_id,
        "timestamp": entry.get("timestamp", datetime.now().isoformat()),
        "app": entry.get("app", "Unknown"),
        "category": entry.get("category", "other"),
    })
    OFFLINE_QUEUE_FILE.write_text(json.dumps(queue, ensure_ascii=False))


def get_queue_size() -> int:
    if not OFFLINE_QUEUE_FILE.exists():
        return 0
    try:
        queue = json.loads(OFFLINE_QUEUE_FILE.read_text())
        return len(queue)
    except Exception:
        return 0


def flush_offline_queue(token: str, device_id: int) -> int:
    if not OFFLINE_QUEUE_FILE.exists():
        return 0
    base = get_backend_url()
    if not base or not token:
        return 0
    try:
        queue = json.loads(OFFLINE_QUEUE_FILE.read_text())
    except (json.JSONDecodeError, IOError):
        return 0
    if not queue:
        return 0
    events = []
    for entry in queue:
        try:
            ts = datetime.fromisoformat(entry["timestamp"])
        except (ValueError, KeyError):
            ts = datetime.now()
        events.append(TimelineEvent(
            app_name=entry.get("app", "Unknown"),
            category=entry.get("category", "other"),
            timestamp=ts,
        ))
    req = TimelineUploadRequest(device_id=device_id, events=events)
    try:
        resp = requests.post(
            f"{base}/api/usage/timeline/upload",
            json=req.model_dump(mode="json"),
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        if resp.status_code == 201:
            uploaded = len(events)
            OFFLINE_QUEUE_FILE.write_text("[]")
            print(f"[sync] Flushed {uploaded} offline events")
            return uploaded
    except Exception:
        pass
    return 0


def generate_schedule(token: str) -> Optional[str]:
    base = get_backend_url()
    if not base:
        return None
    try:
        resp = requests.post(
            f"{base}/api/schedule/generate",
            json={"include_calendar": False},
            headers={"Authorization": f"Bearer {token}"},
            timeout=120,
        )
        if resp.status_code == 200:
            return resp.json()["plan_markdown"]
        else:
            print(f"[sync] Schedule generation failed: {resp.json()}", file=sys.stderr)
            return None
    except Exception as e:
        print(f"[sync] Schedule error: {e}", file=sys.stderr)
        return None


def fetch_latest_schedule(token: str) -> Optional[str]:
    base = get_backend_url()
    if not base:
        return None
    try:
        resp = requests.get(
            f"{base}/api/schedule/latest",
            headers={"Authorization": f"Bearer {token}"},
            timeout=SYNC_TIMEOUT,
        )
        if resp.status_code == 200:
            return resp.json()["plan_markdown"]
        return None
    except Exception as e:
        print(f"[sync] Schedule fetch error: {e}", file=sys.stderr)
        return None
