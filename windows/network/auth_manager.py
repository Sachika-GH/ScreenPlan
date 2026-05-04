"""
auth_manager.py - Token storage using keyring (Windows Credential Manager).
"""
import json
from pathlib import Path
from typing import Optional

import keyring

SERVICE_NAME = "com.screenplan.agent"
ACCOUNT_NAME = "jwt_token"

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


def load_device_id() -> Optional[int]:
    if not DEVICE_STATE_FILE.exists():
        return None
    try:
        state = json.loads(DEVICE_STATE_FILE.read_text())
        return state.get("device_id")
    except (json.JSONDecodeError, IOError):
        return None
