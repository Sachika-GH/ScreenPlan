"""
auth_manager.py - Manages JWT token storage in macOS Keychain.
"""
import json
import subprocess
import sys
from pathlib import Path
from typing import Optional


KEYCHAIN_SERVICE = "com.screenplan.agent"
KEYCHAIN_ACCOUNT = "jwt_token"

DEVICE_STATE_FILE = Path(__file__).resolve().parent.parent / "data" / "device_state.json"


def save_token(token: str) -> bool:
    """Save the JWT token to macOS Keychain."""
    try:
        # Delete existing entry first
        subprocess.run(
            ["security", "delete-generic-password", "-s", KEYCHAIN_SERVICE, "-a", KEYCHAIN_ACCOUNT],
            capture_output=True,
            timeout=5,
        )
        # Add new entry
        proc = subprocess.run(
            ["security", "add-generic-password", "-s", KEYCHAIN_SERVICE, "-a", KEYCHAIN_ACCOUNT, "-w", token],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return proc.returncode == 0
    except Exception as e:
        print(f"[auth] Failed to save token: {e}", file=sys.stderr)
        return False


def load_token() -> Optional[str]:
    """Load the JWT token from macOS Keychain."""
    try:
        proc = subprocess.run(
            ["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-a", KEYCHAIN_ACCOUNT, "-w"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout.strip()
    except Exception as e:
        print(f"[auth] Failed to load token: {e}", file=sys.stderr)
    return None


def delete_token() -> bool:
    """Delete the stored JWT token."""
    try:
        proc = subprocess.run(
            ["security", "delete-generic-password", "-s", KEYCHAIN_SERVICE, "-a", KEYCHAIN_ACCOUNT],
            capture_output=True,
            timeout=5,
        )
        return proc.returncode == 0
    except Exception:
        return False


def save_device_id(device_id: int) -> None:
    """Save device_id to local JSON file."""
    DEVICE_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    state = {}
    if DEVICE_STATE_FILE.exists():
        try:
            state = json.loads(DEVICE_STATE_FILE.read_text())
        except (json.JSONDecodeError, IOError):
            state = {}
    state["device_id"] = device_id
    DEVICE_STATE_FILE.write_text(json.dumps(state))


def load_device_id() -> Optional[int]:
    """Load device_id from local JSON file."""
    if not DEVICE_STATE_FILE.exists():
        return None
    try:
        state = json.loads(DEVICE_STATE_FILE.read_text())
        return state.get("device_id")
    except (json.JSONDecodeError, IOError):
        return None
