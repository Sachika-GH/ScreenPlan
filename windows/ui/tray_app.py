"""
tray_app.py - Windows system tray using pystray.
No popup alerts. Menu updates correctly on toggle.
"""
import threading
import time

import pystray
from PIL import Image, ImageDraw

from network import (
    health_check,
    load_token,
    save_token,
    delete_token,
    upload_timeline_event,
    generate_schedule,
    fetch_latest_schedule,
    get_backend_url,
    load_device_id,
    flush_offline_queue,
    get_queue_size,
)
from tracker import record_current_app


def create_tray_icon():
    img = Image.new("RGB", (64, 64), "white")
    draw = ImageDraw.Draw(img)
    draw.rectangle([16, 8, 48, 56], fill="#238636", outline="#1a6e2b", width=2)
    draw.rectangle([22, 16, 28, 48], fill="white")
    draw.rectangle([36, 16, 42, 48], fill="white")
    return img


class ScreenPlanTray:
    def __init__(self):
        try:
            self.token = load_token()
        except Exception:
            self.token = None
        try:
            self.device_id = load_device_id()
        except Exception:
            self.device_id = None
        self.tracking = False
        self.tracker_thread = None
        self.icon = None

    def _make_menu(self):
        offline = get_queue_size()
        status_extra = f" (离线: {offline}条)" if offline else ""
        status_text = ("已登录" + status_extra) if self.token else "未登录"

        return pystray.Menu(
            pystray.MenuItem(f"状态: {status_text}", lambda: None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("📋 查看最新计划", self._view_plan),
            pystray.MenuItem("🔄 生成今日计划", self._generate_plan),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("⏸ 暂停采集" if self.tracking else "▶️ 开始采集", self._toggle_tracking),
            pystray.MenuItem("⏹ 退出", self._quit),
        )

    def _refresh_menu(self):
        """Update the tray icon's menu in-place."""
        if self.icon:
            self.icon.menu = self._make_menu()

    def _start_tracking(self):
        if self.tracking:
            return
        self.tracking = True
        self._refresh_menu()
        self.tracker_thread = threading.Thread(target=self._tracker_loop, daemon=True)
        self.tracker_thread.start()
        threading.Thread(target=self._flush_loop, daemon=True).start()

    def _toggle_tracking(self, icon, item):
        if self.tracking:
            self.tracking = False
            self._refresh_menu()
        else:
            self._start_tracking()

    def _tracker_loop(self):
        token = load_token()
        device_id = load_device_id()
        interval_seconds = 3 * 60
        while self.tracking:
            try:
                entry = record_current_app()
                print(f"[{entry['time']}] {entry['app']} ({entry['category']})")
                if token and device_id:
                    try:
                        upload_timeline_event(token, device_id, entry)
                    except Exception:
                        pass
            except Exception:
                pass
            time.sleep(interval_seconds)

    def _flush_loop(self):
        while self.tracking:
            time.sleep(60)
            try:
                token = load_token()
                device_id = load_device_id()
                if token and device_id and get_queue_size() > 0:
                    flush_offline_queue(token, device_id)
            except Exception:
                pass

    def _generate_plan(self, icon, item):
        if not self.token:
            return
        generate_schedule(self.token)

    def _view_plan(self, icon, item):
        if not self.token:
            return
        import webbrowser
        webbrowser.open(get_backend_url() or "http://45.197.150.197:5051")

    def _quit(self, icon, item):
        self.tracking = False
        icon.stop()

    def run(self):
        try:
            self.icon = pystray.Icon("screenplan", create_tray_icon(), "ScreenPlan", self._make_menu())
            self._start_tracking()
            self.icon.run()
        except Exception as e:
            print(f"[tray] Failed to start tray icon: {e}")
            print("[tray] This may happen on headless/remote Windows or without Tcl/Tk.")
            print("[tray] Use 'python main.py daemon' for background mode instead.")
            raise


def run_tray():
    app = ScreenPlanTray()
    app.run()
