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

SYSTEM_DIR = Path.home() / "Library" / "Application Support" / "ScreenPlan"
SYSTEM_DEVICE_FILE = SYSTEM_DIR / "device_state.json"

# In frozen .app mode, the bundle is read-only — use SYSTEM_DIR for data files.
if getattr(sys, 'frozen', False):
    DEVICE_STATE_FILE = SYSTEM_DEVICE_FILE
else:
    DEVICE_STATE_FILE = Path(__file__).resolve().parent.parent / "data" / "device_state.json"


def save_token(token: str) -> bool:
    """Save the JWT token to macOS Keychain."""
    try:
        subprocess.run(
            ["security", "delete-generic-password", "-s", KEYCHAIN_SERVICE, "-a", KEYCHAIN_ACCOUNT],
            capture_output=True,
            timeout=5,
        )
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


def save_device_id(device_id: int, key: str = "device_id") -> None:
    """Save a device_id to both system-level and local JSON file."""
    state = {key: device_id}
    payload = json.dumps(state)

    # Save to system-level directory (persists across reinstalls)
    SYSTEM_DIR.mkdir(parents=True, exist_ok=True)
    SYSTEM_DEVICE_FILE.write_text(payload)

    # Save to local data directory
    DEVICE_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    DEVICE_STATE_FILE.write_text(payload)


def load_device_id(key: str = "device_id") -> Optional[int]:
    """Load a device_id. Tries system-level path first, then local fallback."""
    # Try system-level directory first (persists across reinstalls)
    if SYSTEM_DEVICE_FILE.exists():
        try:
            state = json.loads(SYSTEM_DEVICE_FILE.read_text())
            if key in state:
                return state[key]
        except (json.JSONDecodeError, IOError):
            pass

    # Fallback to local data directory
    if DEVICE_STATE_FILE.exists():
        try:
            state = json.loads(DEVICE_STATE_FILE.read_text())
            return state.get(key)
        except (json.JSONDecodeError, IOError):
            pass

    return None


def save_device_identity(device_id: int, server_url: Optional[str] = None) -> None:
    """Save device identity to system-level directory for persistence across reinstalls."""
    SYSTEM_DIR.mkdir(parents=True, exist_ok=True)
    state = {"device_id": device_id}
    if server_url:
        state["server_url"] = server_url
    SYSTEM_DEVICE_FILE.write_text(json.dumps(state))

    # Also save to local data directory
    DEVICE_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    DEVICE_STATE_FILE.write_text(json.dumps(state))
