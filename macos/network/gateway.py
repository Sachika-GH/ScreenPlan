"""
gateway.py - Resolve ScreenPlan backend URL.
Priority: config.json server_url > LAN gateway auto-detection > environment variable.
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
    if getattr(sys, 'frozen', False):
        return Path(sys.argv[0]).resolve().parent / 'config.json'
    return Path(__file__).resolve().parent.parent / "config.json"


def _load_config() -> dict:
    config_path = _get_config_path()
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def get_server_url() -> Optional[str]:
    """
    Resolve the ScreenPlan backend URL.
    Priority:
      1. config.json → server.url
      2. SCREENPLAN_SERVER_URL environment variable
      3. LAN gateway auto-detection (http://<gateway>:5051)
    """
    # 1. Config file
    config = _load_config()
    configured = config.get("server", {}).get("url", "")
    if configured:
        url = configured.rstrip("/")
        if not url.startswith("http"):
            url = f"http://{url}"
        return url

    # 2. Environment variable
    env_url = os.environ.get("SCREENPLAN_SERVER_URL", "")
    if env_url:
        url = env_url.rstrip("/")
        if not url.startswith("http"):
            url = f"http://{url}"
        return url

    # 3. LAN gateway auto-detection
    gateway = get_default_gateway()
    if gateway:
        return f"http://{gateway}:{DEFAULT_PORT}"

    return None


def get_default_gateway() -> Optional[str]:
    """Get the default gateway IP from routing table."""
    try:
        proc = subprocess.run(
            ["netstat", "-rn", "-f", "inet"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if proc.returncode != 0:
            return None

        for line in proc.stdout.split("\n"):
            parts = line.split()
            if len(parts) >= 2 and parts[0] == "default":
                gateway = parts[1]
                try:
                    socket.inet_aton(gateway)
                    return gateway
                except OSError:
                    continue
    except Exception as e:
        print(f"[gateway] Failed to detect gateway: {e}", file=sys.stderr)

    return None


def is_backend_reachable(host: str, port: int = 5051, timeout: float = 3.0) -> bool:
    """Check if the ScreenPlan backend is reachable on a host:port."""
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.close()
        return True
    except (OSError, socket.timeout):
        return False
