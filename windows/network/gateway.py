"""
gateway.py - Resolve ScreenPlan backend URL on Windows.
Priority: config.json server_url > env var > LAN gateway detection.
"""
import json
import os
import subprocess
import sys
import socket
from pathlib import Path
from typing import Optional


DEFAULT_PORT = 5051


def _get_config_path() -> Path:
    return Path(__file__).resolve().parent.parent / "config.json"


def _load_config() -> dict:
    config_path = _get_config_path()
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def get_server_url() -> Optional[str]:
    config = _load_config()
    configured = config.get("server", {}).get("url", "")
    if configured:
        url = configured.rstrip("/")
        if not url.startswith("http"):
            url = f"http://{url}"
        return url

    env_url = os.environ.get("SCREENPLAN_SERVER_URL", "")
    if env_url:
        url = env_url.rstrip("/")
        if not url.startswith("http"):
            url = f"http://{url}"
        return url

    gateway = get_default_gateway()
    if gateway:
        return f"http://{gateway}:{DEFAULT_PORT}"

    return None


def get_default_gateway() -> Optional[str]:
    """Get the default gateway IP from Windows routing table via 'route print'.
    This approach is language-independent (unlike ipconfig output parsing)."""
    try:
        proc = subprocess.run(
            ["route", "print", "0.0.0.0"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        for line in proc.stdout.split("\n"):
            line = line.strip()
            if line.startswith("0.0.0.0") and "0.0.0.0" in line:
                parts = line.split()
                if len(parts) >= 3:
                    gateway = parts[2]
                    if gateway != "0.0.0.0":
                        try:
                            socket.inet_aton(gateway)
                            return gateway
                        except OSError:
                            continue
    except Exception as e:
        print(f"[gateway] Failed to detect gateway: {e}", file=sys.stderr)
    return None


def is_backend_reachable(host: str, port: int = 5051, timeout: float = 3.0) -> bool:
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.close()
        return True
    except (OSError, socket.timeout):
        return False
