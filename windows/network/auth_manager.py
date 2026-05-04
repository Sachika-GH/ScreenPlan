"""
auth_manager.py - Token storage using keyring (Windows Credential Manager).
"""
import json
import os
import sys
from pathlib import Path
from typing import Optional

import keyring

SERVICE_NAME = "com.screenplan.agent"
ACCOUNT_NAME = "jwt_token"

APPDATA_DIR = Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))) / "ScreenPlan"
SYSTEM_DEVICE_FILE = APPDATA_DIR / "device_state.json"

# In frozen .exe mode, the bundle is read-only — use APPDATA for data files.
if getattr(sys, 'frozen', False):
    DEVICE_STATE_FILE = SYSTEM_DEVICE_FILE
else:
    DEVICE_STATE_FILE = Path(__file__).resolve().parent.parent / "data" / "device_state.json"


def save_token(token: str) -> None:
    try:
        keyring.set_password(SERVICE_NAME, ACCOUNT_NAME, token)
    except Exception:
        # Fallback: store to file
        from pathlib import Path
        f = Path(__file__).resolve().parent.parent / "data" / ".token"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(token)


def load_token() -> Optional[str]:
    try:
        return keyring.get_password(SERVICE_NAME, ACCOUNT_NAME)
    except Exception:
        pass
    # Fallback: read from file
    f = Path(__file__).resolve().parent.parent / "data" / ".token"
    if f.exists():
        return f.read_text().strip()
    return None


def delete_token() -> None:
    try:
        keyring.delete_password(SERVICE_NAME, ACCOUNT_NAME)
    except Exception:
        pass


def save_device_id(device_id: int) -> None:
    DEVICE_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    state = {"device_id": device_id}
    DEVICE_STATE_FILE.write_text(json.dumps(state))
    APPDATA_DIR.mkdir(parents=True, exist_ok=True)
    SYSTEM_DEVICE_FILE.write_text(json.dumps(state))


def load_device_id() -> Optional[int]:
    if SYSTEM_DEVICE_FILE.exists():
        try:
            state = json.loads(SYSTEM_DEVICE_FILE.read_text())
            return state.get("device_id")
        except (json.JSONDecodeError, IOError):
            pass
    if not DEVICE_STATE_FILE.exists():
        return None
    try:
        state = json.loads(DEVICE_STATE_FILE.read_text())
        return state.get("device_id")
    except (json.JSONDecodeError, IOError):
        return None


def save_device_identity(device_id, server_url=None):
    """Save device identity to system-level AppData directory."""
    APPDATA_DIR.mkdir(parents=True, exist_ok=True)
    state = {"device_id": device_id}
    if server_url:
        state["server_url"] = server_url
    SYSTEM_DEVICE_FILE.write_text(json.dumps(state))
