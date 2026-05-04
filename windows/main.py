"""
main.py - ScreenPlan Windows Agent entry point.

Usage:
    python main.py tray      # System tray app (GUI)
    python main.py daemon    # Background tracker (no UI)
    python main.py setup     # First-time setup wizard
    python main.py status    # Check connection status
"""
import argparse
import sys
import json
from datetime import date, datetime
from pathlib import Path
from getpass import getpass

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


def cmd_setup():
    print("=" * 50)
    print("  ScreenPlan Windows Agent - First Setup")
    print("=" * 50)
    print()

    url = get_backend_url()
    if not url:
        print("No backend configured. Edit config.json server.url")
        return

    print(f"Backend: {url}")
    health = health_check()
    if health:
        print(f"Backend online (v{health.version})")
    else:
        print("Backend unreachable. Check server and network.")
        return

    print()
    choice = input("Existing account? (y/n): ").strip().lower()

    if choice == "y":
        email = input("Email: ").strip()
        password = getpass("Password: ").strip()
        resp = login(email, password)
        if not resp:
            print("Login failed.")
            return
    else:
        family = input("Family name: ").strip()
        email = input("Email: ").strip()
        password = getpass("Password: ").strip()
        display = input("Display name: ").strip()
        resp = register(family, email, password, display)
        if not resp:
            print("Registration failed.")
            return

    save_token(resp.access_token)
    print(f"Login successful! Welcome, {resp.display_name}")

    device_name = input(f"\nDevice name (e.g. Gaming PC): ").strip() or "WindowsPC"
    device_id = register_device(resp.access_token, device_name, "windows")
    if device_id:
        save_device_id(device_id)
        print(f"Device registered (ID: {device_id})")
    else:
        print("Device registration failed, but continuing.")
        # Try to get existing device ID from backend
        try:
            import requests
            r = requests.get(f"{url}/api/devices", headers={"Authorization": f"Bearer {resp.access_token}"}, timeout=10)
            for d in r.json():
                if d["platform"] == "windows":
                    save_device_id(d["id"])
                    print(f"Found existing device (ID: {d['id']})")
                    break
        except Exception:
            pass

    print("\nSetup complete!")
    print("  python main.py tray     -> Start system tray")
    print("  python main.py daemon   -> Start background tracker")


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
        print("[main] WARNING: Not logged in. Run 'python main.py setup' first.")
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
    parser = argparse.ArgumentParser(description="ScreenPlan Windows Agent")
    parser.add_argument("command", choices=["tray", "daemon", "setup", "status"])
    args = parser.parse_args()

    commands = {
        "tray": cmd_tray,
        "daemon": cmd_daemon,
        "setup": cmd_setup,
        "status": cmd_status,
    }
    commands[args.command]()


if __name__ == "__main__":
    main()
