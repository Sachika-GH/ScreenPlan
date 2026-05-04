"""
tray_app.py - macOS system tray UI using rumps.
No popup alerts — network failures handled silently via offline queue.
"""
import threading
import time
import sys
from datetime import date, timedelta

import rumps

from tracker import record_current_app, read_activity_log
from network import (
    health_check,
    load_token,
    save_token,
    delete_token,
    register_device,
    generate_schedule,
    fetch_latest_schedule,
    get_backend_url,
    upload_timeline_event,
    load_device_id,
    flush_offline_queue,
    get_queue_size,
)


class ScreenPlanTrayApp(rumps.App):
    def __init__(self, auto_start_tracking=False):
        super().__init__("ScreenPlan", title="▶️" if auto_start_tracking else "📊")
        self.token = load_token()
        self.device_id = load_device_id()
        self.tracking = auto_start_tracking
        self.tracker_thread = None
        self._setup_menu()
        if auto_start_tracking:
            self.tracker_thread = threading.Thread(target=self._tracker_loop, daemon=True)
            self.tracker_thread.start()
        # Periodic status + offline queue flush
        rumps.Timer(self._on_tick, 60).start()

    def _setup_menu(self):
        self.status_item = rumps.MenuItem("状态: 未连接", callback=None)
        self.menu.clear()
        self.menu.add(self.status_item)
        self.menu.add(rumps.separator)
        self.menu.add(rumps.MenuItem("📋 查看最新计划", callback=self.view_plan))
        self.menu.add(rumps.MenuItem("🔄 立即生成计划", callback=self.generate_plan_now))
        self.menu.add(rumps.separator)
        if self.tracking:
            self.menu.add(rumps.MenuItem("⏸ 暂停采集", callback=self.toggle_tracking))
        else:
            self.menu.add(rumps.MenuItem("▶️ 开始采集", callback=self.toggle_tracking))
        self.menu.add(rumps.separator)
        self.menu.add(rumps.MenuItem("登出", callback=self.logout))
        self.menu.add(rumps.MenuItem("退出", callback=self.quit_app))

    def _on_tick(self, _):
        self._update_status()
        self._try_flush_queue()

    def _update_status(self):
        backend_url = get_backend_url()
        if not backend_url:
            self.status_item.title = "状态: 🔴 未配置服务器"
            self.title = "📊"
            return

        health = health_check()
        offline = get_queue_size()

        if not health:
            extra = f" (离线: {offline}条)" if offline else ""
            self.status_item.title = f"状态: 🔴 离线{extra}"
            self.title = "📊"
            return

        if not self.token:
            self.token = load_token()
        if not self.device_id:
            self.device_id = load_device_id()

        if self.token:
            extra = f" (离线: {offline}条)" if offline else ""
            self.status_item.title = f"状态: ✅ 已连接{extra}"
            self.title = "📊"
        else:
            self.status_item.title = "状态: ⚠️ 在线 · 未登录"
            self.title = "📊"

    def _try_flush_queue(self):
        if not self.token or not self.device_id:
            return
        if get_queue_size() > 0:
            flush_offline_queue(self.token, self.device_id)

    def toggle_tracking(self, _):
        self.tracking = not self.tracking
        if self.tracking:
            self.tracker_thread = threading.Thread(target=self._tracker_loop, daemon=True)
            self.tracker_thread.start()
        self._setup_menu()

    def _tracker_loop(self):
        interval_seconds = 3 * 60  # matches config
        token = load_token()
        device_id = load_device_id()
        t0 = time.monotonic()
        while self.tracking:
            t1 = time.monotonic()
            elapsed = t1 - t0
            drift = elapsed - interval_seconds
            if drift > interval_seconds * 2:
                print(f"[tracker] Sleep/wake detected (drift={drift:.0f}s)",
                      file=sys.stderr)
            t0 = time.monotonic()

            try:
                entry = record_current_app()
                if entry is not None:
                    url_info = ""
                    if entry.get("url"):
                        url_info = f" | {entry['url']}"
                    print(f"[{entry['time']}] {entry['app']} ({entry['category']}){url_info}")
                    if token and device_id:
                        try:
                            upload_timeline_event(token, device_id, entry)
                        except Exception:
                            pass
            except Exception:
                pass
            time.sleep(interval_seconds)

    def generate_plan_now(self, _):
        if not self.token:
            return
        self.status_item.title = "状态: ⏳ 正在生成计划..."
        plan = generate_schedule(self.token, include_calendar=True)
        if plan:
            self.status_item.title = "状态: ✅ 计划已生成"
        else:
            self.status_item.title = "状态: ❌ 生成失败 (检查 API Key)"

    def view_plan(self, _):
        if not self.token:
            return
        plan = fetch_latest_schedule(self.token)
        if plan:
            rumps.alert("最新计划", plan[:2000])
        else:
            rumps.alert("暂无计划", "还没有生成过计划，请先生成。")

    def logout(self, _):
        delete_token()
        self.token = None
        self.device_id = None
        self._update_status()

    def quit_app(self, _):
        self.tracking = False
        rumps.quit_application()


def run_tray(auto_start_tracking=False):
    app = ScreenPlanTrayApp(auto_start_tracking=auto_start_tracking)
    app.run()
