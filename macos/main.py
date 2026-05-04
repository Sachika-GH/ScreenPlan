"""
main.py - ScreenPlan macOS Agent entry point.

Usage:
    python3 main.py tray              # Run system tray app
    python3 main.py daemon            # Run activity tracker daemon (no UI)
    python3 main.py sync              # Sync yesterday's data to router
    python3 main.py plan              # Generate and view today's plan
    python3 main.py status            # Check agent and backend status
"""
import argparse
import sys
import json
import time
from datetime import date, timedelta
from pathlib import Path

from tracker import read_activity_log
from network import (
    health_check,
    login,
    register,
    load_token,
    save_token,
    delete_token,
    register_device,
    sync_yesterday,
    generate_schedule,
    fetch_latest_schedule,
    get_backend_url,
    upload_timeline_event,
    save_device_id,
    load_device_id,
    flush_offline_queue,
    get_queue_size,
)
from tracker import run_tracker_loop


def cmd_tray():
    """Run the system tray application. Use --autostart to begin tracking immediately."""
    auto_start = "--autostart" in sys.argv
    try:
        from ui import run_tray
        run_tray(auto_start_tracking=auto_start)
    except ImportError:
        print("Need rumps: pip3 install rumps", file=sys.stderr)
        sys.exit(1)


def cmd_daemon():
    """Run activity tracker in background (no UI), with real-time upload + offline queue flush."""
    import threading

    print("[main] Starting activity tracker daemon (real-time upload)...")

    token = load_token()
    device_id = load_device_id()

    if not token or not device_id:
        print("[main] WARNING: Not logged in. Launch the ScreenPlan tray app to set up.")
        print("[main] Running in offline mode - data saved locally only.")
        run_tracker_loop()
        return

    print(f"[main] Token loaded, device_id={device_id}")

    config = {}
    config_path = Path(__file__).resolve().parent / "config.json"
    if config_path.exists():
        with open(config_path, "r") as f:
            config = json.load(f)

    def on_record(entry: dict):
        """Callback: upload each recorded app event. Queues offline on failure."""
        upload_timeline_event(token, device_id, entry)

    def flush_loop():
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


def cmd_sync():
    """Sync yesterday's data to the router."""
    token = load_token()
    if not token:
        print("Not logged in. Launch the ScreenPlan tray app to set up.")
        return

    config = {}
    config_path = Path(__file__).resolve().parent / "config.json"
    if config_path.exists():
        with open(config_path, "r") as f:
            config = json.load(f)

    interval = config.get("tracker", {}).get("record_interval_minutes", 20)
    yesterday = date.today() - timedelta(days=1)
    records = read_activity_log(yesterday)

    print(f"Syncing {len(records)} records...")
    ok = sync_yesterday(token, 1, records, interval)
    print("Sync OK" if ok else "Sync FAILED")


def cmd_plan():
    """Generate and display today's plan."""
    token = load_token()
    if not token:
        print("Not logged in. Launch the ScreenPlan tray app to set up.")
        return

    print("Generating today's plan...")
    plan = generate_schedule(token, include_calendar=True)
    if plan:
        print("\n" + "=" * 50)
        print(plan)
        print("=" * 50)
        print("\nPlan saved to cloud, view in Web UI")
    else:
        print("Plan generation failed. Check LLM API Key config on router.")


def cmd_status():
    """Check agent and backend status."""
    print("ScreenPlan macOS Agent\n")

    token = load_token()
    print(f"Login status: {'Logged in' if token else 'Not logged in'}")

    url = get_backend_url()
    print(f"Backend URL: {url or 'Not detected'}")

    health = health_check()
    if health:
        print(f"Backend: Online (v{health.version}, {health.user_count} users)")
    else:
        print("Backend: Unreachable")


def main():
    # When launched via double-clicked .app (py2app), no args are passed.
    # Default to tray mode.
    parser = argparse.ArgumentParser(description="ScreenPlan macOS Agent")
    parser.add_argument(
        "command",
        nargs="?",
        default="tray",
        choices=["tray", "daemon", "sync", "plan", "status"],
        help="Run mode (default: tray)",
    )
    args, unknown = parser.parse_known_args()

    commands = {
        "tray": cmd_tray,
        "daemon": cmd_daemon,
        "sync": cmd_sync,
        "plan": cmd_plan,
        "status": cmd_status,
    }
    commands[args.command]()


if __name__ == "__main__":
    main()
