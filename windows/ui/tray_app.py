"""
tray_app.py - Windows system tray using pystray.
Setup flow with tkinter login window, auto-start toggle, APPDATA persistence.
"""
import os
import threading
import time
from pathlib import Path

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
    save_device_id,
    save_device_identity,
    register_device,
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
        self.appdata = Path(os.environ.get("APPDATA", "")) / "ScreenPlan"
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

        if not self.token:
            self._setup_flow()
        elif not self.device_id:
            self._device_naming_flow()

    def _setup_flow(self):
        from ui.setup_window import SetupWindow
        SetupWindow(on_success=self._on_setup_complete)

    def _on_setup_complete(self, token, display_name):
        self.token = token
        self._device_naming_flow()

    def _device_naming_flow(self):
        existing = self._find_existing_device()
        if existing:
            self.device_id = existing
            save_device_id(existing)
            save_device_identity(existing)
            return

        import tkinter as tk
        from tkinter import simpledialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        name = simpledialog.askstring("ScreenPlan", "设备名称 (e.g. Gaming PC):", parent=root)
        root.destroy()
        if not name:
            name = "WindowsPC"

        device_id = register_device(self.token, name, "windows")
        if device_id:
            self.device_id = device_id
            save_device_id(device_id)
            save_device_identity(device_id)

    def _find_existing_device(self):
        url = get_backend_url()
        if not url or not self.token:
            return None
        try:
            import requests
            r = requests.get(
                f"{url}/api/devices",
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=10,
            )
            for d in r.json():
                if d.get("platform") == "windows":
                    return d["id"]
        except Exception:
            pass
        return None

    def _check_setup(self):
        return bool(self.token and self.device_id)

    def _make_menu(self):
        offline = get_queue_size()
        status_extra = f" (离线: {offline}条)" if offline else ""
        status_text = ("已登录" + status_extra) if self.token else "未登录"

        try:
            from network import autostart
            auto_enabled = autostart.is_autostart_enabled()
        except Exception:
            auto_enabled = False
        auto_text = "✅ 开机自启" if auto_enabled else "⬜ 开机自启"

        return pystray.Menu(
            pystray.MenuItem(f"状态: {status_text}", lambda: None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("📋 查看最新计划", self._view_plan),
            pystray.MenuItem("🔄 生成今日计划", self._generate_plan),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(auto_text, self._toggle_autostart),
            pystray.MenuItem("⏸ 暂停采集" if self.tracking else "▶️ 开始采集", self._toggle_tracking),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("⏹ 退出", self._quit),
        )

    def _refresh_menu(self):
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

    def _toggle_autostart(self, icon, item):
        try:
            from network import autostart
            if autostart.is_autostart_enabled():
                autostart.disable_autostart()
            else:
                autostart.enable_autostart()
            self._refresh_menu()
        except Exception:
            pass

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
        if not self._check_setup():
            return
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
