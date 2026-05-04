"""
main.py - ScreenPlan macOS Agent entry point.

Usage:
    python3 main.py tray              # Run system tray app
    python3 main.py daemon            # Run activity tracker daemon (no UI)
    python3 main.py sync              # Sync yesterday's data to router
    python3 main.py plan              # Generate and view today's plan
    python3 main.py setup             # First-time setup wizard
    python3 main.py status            # Check agent and backend status
"""
import argparse
import sys
import json
import time
from datetime import date, timedelta
from pathlib import Path
from getpass import getpass

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


def cmd_setup():
    """First-time setup wizard."""
    print("=" * 50)
    print("  ScreenPlan macOS Agent - 首次设置")
    print("=" * 50)
    print()

    # Check backend
    url = get_backend_url()
    if not url:
        print("❌ 未检测到路由器。请确保已连接到家庭 WiFi。")
        return

    print(f"路由器地址: {url}")
    health = health_check()
    if health:
        print(f"✅ 后端在线 (v{health.version})")
    else:
        print("❌ 后端不可达。请检查路由器上的 ScreenPlan 服务是否运行。")
        return

    print()
    choice = input("是否已有账户？(y/n): ").strip().lower()

    if choice == "y":
        email = input("邮箱: ").strip()
        password = getpass("密码: ").strip()
        resp = login(email, password)
        if not resp:
            print("❌ 登录失败。")
            return
    else:
        family = input("家庭名称: ").strip()
        email = input("邮箱: ").strip()
        password = getpass("密码: ").strip()
        display = input("显示名称: ").strip()
        resp = register(family, email, password, display)
        if not resp:
            print("❌ 注册失败。")
            return

    save_token(resp.access_token)
    print(f"✅ 登录成功! 欢迎, {resp.display_name}")

    # Register device
    device_name = input(f"\n此设备名称 (如 MacBook Pro): ").strip() or "Mac"
    device_id = register_device(resp.access_token, device_name, "macos")
    if device_id:
        save_device_id(device_id)
        print(f"✅ 设备已注册 (ID: {device_id})")
    else:
        print("⚠️ 设备注册失败，但可继续使用。")

    print("\n设置完成！运行 python3 main.py tray 启动托盘应用。")
    print("或运行 python3 main.py daemon 启动后台采集。")


def cmd_tray():
    """Run the system tray application. Use --autostart to begin tracking immediately."""
    auto_start = "--autostart" in sys.argv
    try:
        from ui import run_tray
        run_tray(auto_start_tracking=auto_start)
    except ImportError:
        print("需要安装 rumps: pip3 install rumps", file=sys.stderr)
        sys.exit(1)


def cmd_daemon():
    """Run activity tracker in background (no UI), with real-time upload + offline queue flush."""
    import threading

    print("[main] Starting activity tracker daemon (real-time upload)...")

    token = load_token()
    device_id = load_device_id()

    if not token or not device_id:
        print("[main] WARNING: Not logged in. Run 'python3 main.py setup' first.")
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

    # Background flush thread — retries queued events every 60s
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
        print("未登录。请先运行 python3 main.py setup")

    config = {}
    config_path = Path(__file__).resolve().parent / "config.json"
    if config_path.exists():
        with open(config_path, "r") as f:
            config = json.load(f)

    interval = config.get("tracker", {}).get("record_interval_minutes", 20)
    yesterday = date.today() - timedelta(days=1)
    records = read_activity_log(yesterday)

    print(f"同步 {len(records)} 条记录...")
    # device_id would be stored alongside token in a full implementation
    # For now, we use a best-effort approach
    ok = sync_yesterday(token, 1, records, interval)  # TODO: store device_id
    print("✅ 同步完成" if ok else "❌ 同步失败")


def cmd_plan():
    """Generate and display today's plan."""
    token = load_token()
    if not token:
        print("未登录。请先运行 python3 main.py setup")
        return

    print("正在生成今日计划...")
    plan = generate_schedule(token, include_calendar=True)
    if plan:
        print("\n" + "=" * 50)
        print(plan)
        print("=" * 50)
        print("\n✅ 计划已保存到云端，访问 Web UI 查看")
    else:
        print("❌ 计划生成失败。请检查路由器上的 LLM API Key 配置。")


def cmd_status():
    """Check agent and backend status."""
    print("ScreenPlan macOS Agent\n")

    token = load_token()
    print(f"登录状态: {'✅ 已登录' if token else '❌ 未登录'}")

    url = get_backend_url()
    print(f"路由器地址: {url or '未检测到'}")

    health = health_check()
    if health:
        print(f"后端状态: ✅ 在线 (v{health.version}, {health.user_count} 用户)")
    else:
        print("后端状态: ❌ 不可达")


def main():
    parser = argparse.ArgumentParser(description="ScreenPlan macOS Agent")
    parser.add_argument(
        "command",
        choices=["tray", "daemon", "sync", "plan", "setup", "status"],
        help="运行模式",
    )
    args, unknown = parser.parse_known_args()

    commands = {
        "tray": cmd_tray,
        "daemon": cmd_daemon,
        "sync": cmd_sync,
        "plan": cmd_plan,
        "setup": cmd_setup,
        "status": cmd_status,
    }
    commands[args.command]()


if __name__ == "__main__":
    main()
