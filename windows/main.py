"""
main.py - ScreenPlan Windows Agent entry point.

Usage:
    python main.py tray      # System tray app (GUI)
    python main.py daemon    # Background tracker (no UI)
    python main.py exe       # PyInstaller .exe entry point
    python main.py status    # Check connection status
"""
import argparse
import os
import sys
import json
from datetime import date, datetime
from pathlib import Path

from network import (
    health_check,
    login,
    register,
    load_token,
    save_token,
    delete_token,
    register_device,
    upload_timeline_event,
    generate_schedule,
    fetch_latest_schedule,
    get_backend_url,
    save_device_id,
    load_device_id,
    flush_offline_queue,
    get_queue_size,
)
from tracker import run_tracker_loop


def cmd_exe():
    """Entry point for .exe packaging (PyInstaller compatible)."""
    import os
    if getattr(sys, 'frozen', False):
        os.chdir(os.path.dirname(sys.executable))
    cmd_tray()


def cmd_tray():
    try:
        from ui import run_tray
        run_tray()
    except ImportError as e:
        print(f"Missing dependency: {e}", file=sys.stderr)
        print("Run: pip install pystray pillow", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Tray failed to start: {e}", file=sys.stderr)
        print("This may happen on headless/remote Windows environments.", file=sys.stderr)
        print("Use daemon mode instead: python main.py daemon", file=sys.stderr)
        sys.exit(1)


def cmd_daemon():
    import threading
    print("[main] Starting tracker daemon with real-time upload + offline queue...")
    token = load_token()
    device_id = load_device_id()

    if not token or not device_id:
        print("[main] WARNING: Not logged in. Launch the ScreenPlan tray app to set up.")
        print("[main] Running in offline mode - data saved locally only.")
        run_tracker_loop()
        return

    print(f"[main] Token loaded, device_id={device_id}")

    def on_record(entry):
        upload_timeline_event(token, device_id, entry)

    def flush_loop():
        import time
        while True:
            time.sleep(60)
            try:
                q = get_queue_size()
                if q > 0:
                    flushed = flush_offline_queue(token, device_id)
                    if flushed:
                        print(f"[main] Flushed {flushed} offline events")
            except Exception:
                pass

    threading.Thread(target=flush_loop, daemon=True).start()
    run_tracker_loop(record_callback=on_record)


def cmd_status():
    print("ScreenPlan Windows Agent\n")
    token = load_token()
    print(f"Login: {'Logged in' if token else 'Not logged in'}")
    url = get_backend_url()
    print(f"Backend: {url or 'Not configured'}")
    device_id = load_device_id()
    print(f"Device ID: {device_id or 'Not registered'}")
    health = health_check()
    if health:
        print(f"Backend: Online (v{health.version}, {health.user_count} users)")
    else:
        print("Backend: Unreachable")


def main():
    # In windowed .exe mode (--noconsole), sys.stdout/stderr are None.
    # Redirect to devnull to prevent argparse/print from crashing.
    if sys.stdout is None:
        sys.stdout = open(os.devnull, 'w')
    if sys.stderr is None:
        sys.stderr = open(os.devnull, 'w')

    parser = argparse.ArgumentParser(description="ScreenPlan Windows Agent")
    parser.add_argument("command", nargs="?", default="tray",
                        choices=["tray", "daemon", "exe", "status"])
    args = parser.parse_args()

    commands = {
        "tray": cmd_tray,
        "daemon": cmd_daemon,
        "exe": cmd_exe,
        "status": cmd_status,
    }
    commands[args.command]()


if __name__ == "__main__":
    main()
