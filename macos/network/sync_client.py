"""
sync_client.py - Syncs activity data to the ScreenPlan backend (router or VPS).
"""
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import requests

from network.gateway import get_server_url
from network.auth_manager import load_token
from protocol_models import (
    UsageRecord, UsageUploadRequest, AuthResponse, HealthResponse,
    TimelineEvent, TimelineUploadRequest,
)


BACKEND_PORT = 5051
SYNC_TIMEOUT = 15

OFFLINE_QUEUE_FILE = (
    Path.home() / "Library" / "Application Support" / "ScreenPlan" / "offline_queue.json"
    if getattr(sys, 'frozen', False)
    else Path(__file__).resolve().parent.parent / "data" / "offline_queue.json"
)


def get_backend_url() -> Optional[str]:
    return get_server_url()


def health_check() -> Optional[HealthResponse]:
    """Check if the backend is reachable and healthy."""
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
    """Attempt login to the backend."""
    base = get_backend_url()
    if not base:
        print("[sync] No backend found", file=sys.stderr)
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
            err = resp.json().get("error", "Unknown error")
            print(f"[sync] Login failed: {err}", file=sys.stderr)
            return None
    except Exception as e:
        print(f"[sync] Login error: {e}", file=sys.stderr)
        return None


def register(family_name: str, email: str, password: str, display_name: str) -> Optional[AuthResponse]:
    """Register a new user."""
    base = get_backend_url()
    if not base:
        return None

    try:
        resp = requests.post(
            f"{base}/api/auth/register",
            json={
                "family_name": family_name,
                "email": email,
                "password": password,
                "display_name": display_name,
            },
            timeout=SYNC_TIMEOUT,
        )
        if resp.status_code == 201:
            return AuthResponse(**resp.json())
        else:
            err = resp.json().get("error", "Unknown error")
            print(f"[sync] Register failed: {err}", file=sys.stderr)
            return None
    except Exception as e:
        print(f"[sync] Register error: {e}", file=sys.stderr)
        return None


def register_device(token: str, name: str, platform: str = "macos") -> Optional[int]:
    """Register a device and return its ID."""
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


def upload_usage(token: str, device_id: int, target_date: date, records: list[dict]) -> bool:
    """Upload usage records for a given date."""
    if not records:
        return True

    base = get_backend_url()
    if not base:
        return False

    usage_records = [
        UsageRecord(
            app_name=r["app_name"],
            category=r["category"],
            duration_minutes=r["duration_minutes"],
        )
        for r in records
    ]

    request = UsageUploadRequest(
        device_id=device_id,
        date=target_date,
        records=usage_records,
    )

    try:
        resp = requests.post(
            f"{base}/api/usage/upload",
            json=request.model_dump(mode="json"),
            headers={"Authorization": f"Bearer {token}"},
            timeout=SYNC_TIMEOUT,
        )
        if resp.status_code == 201:
            return True
        else:
            print(f"[sync] Upload failed: {resp.json()}", file=sys.stderr)
            return False
    except Exception as e:
        print(f"[sync] Upload error: {e}", file=sys.stderr)
        return False


def sync_yesterday(token: str, device_id: int, raw_records: list[dict], interval_minutes: int = 20) -> bool:
    """Sync yesterday's activity data to the backend."""
    if not raw_records:
        print("[sync] No records to sync")
        return True

    yesterday = date.today() - timedelta(days=1)

    from analyzer import aggregate_usage_for_upload
    records = aggregate_usage_for_upload(raw_records)
    print(f"[sync] Syncing {len(records)} apps for {yesterday.isoformat()}")
    return upload_usage(token, device_id, yesterday, records)


def fetch_summary(token: str, target_date: Optional[date] = None) -> Optional[dict]:
    """Fetch usage summary from the backend."""
    base = get_backend_url()
    if not base:
        return None

    from datetime import date as date_type
    d = target_date or date_type.today()

    try:
        resp = requests.get(
            f"{base}/api/usage/summary?date={d.isoformat()}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=SYNC_TIMEOUT,
        )
        if resp.status_code == 200:
            return resp.json()
        return None
    except Exception as e:
        print(f"[sync] Summary fetch error: {e}", file=sys.stderr)
        return None


def generate_schedule(token: str, include_calendar: bool = False) -> Optional[str]:
    """Request schedule generation and return the plan markdown."""
    base = get_backend_url()
    if not base:
        return None

    try:
        resp = requests.post(
            f"{base}/api/schedule/generate",
            json={"include_calendar": include_calendar},
            headers={"Authorization": f"Bearer {token}"},
            timeout=120,  # LLM call can be slow
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
    """Fetch the latest generated schedule."""
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


def upload_timeline_event(token: str, device_id: int, entry: dict) -> bool:
    """Upload a single foreground-app event in real time.
    On failure, queues to offline file for later retry.
    Skips Unknown entries (idle/sleep periods)."""
    if entry.get("app", "Unknown") == "Unknown":
        return False

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
    """Save a failed upload to local offline queue for later retry."""
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
    """Return number of pending offline events."""
    if not OFFLINE_QUEUE_FILE.exists():
        return 0
    try:
        queue = json.loads(OFFLINE_QUEUE_FILE.read_text())
        return len(queue)
    except Exception:
        return 0


def flush_offline_queue(token: str, device_id: int) -> int:
    """Attempt to upload all queued offline events. Returns count of successfully uploaded."""
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

    # Build batch request
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
