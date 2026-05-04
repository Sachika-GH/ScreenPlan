"""
tray_app.py - macOS system tray UI using rumps.
No popup alerts - network failures handled silently via offline queue.
"""
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import rumps

from tracker import record_current_app, read_activity_log
from network import (
    health_check,
    login,
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
from network.auth_manager import (
    save_device_id,
    save_device_identity,
    SYSTEM_DIR,
    SYSTEM_DEVICE_FILE,
    DEVICE_STATE_FILE,
)

PLIST_LABEL = "com.screenplan.tray"


class ScreenPlanTrayApp(rumps.App):
    def __init__(self, auto_start_tracking=False):
        super().__init__("ScreenPlan", title="\u25b6\ufe0f" if auto_start_tracking else "\U0001f4ca")
        self.token = load_token()
        self.device_id = self._resolve_device_id()
        self.tracking = False
        self.tracker_thread = None
        self._cleanup_old_launchd()
        self._setup_menu()
        if auto_start_tracking and self.token and self.device_id:
            self.tracking = True
            self.tracker_thread = threading.Thread(target=self._tracker_loop, daemon=True)
            self.tracker_thread.start()
        rumps.Timer(self._on_tick, 60).start()
        if not self.token or not self.device_id:
            rumps.Timer(self._deferred_setup, 0.5).start()

    @staticmethod
    def _cleanup_old_launchd():
        """Unload and remove leftover launchd plists from previous installations."""
        old_labels = ["com.screenplan.agent", "com.screenplan.tray"]
        for label in old_labels:
            plist = Path.home() / "Library" / "LaunchAgents" / f"{label}.plist"
            if plist.exists():
                try:
                    subprocess.run(["launchctl", "unload", str(plist)],
                                   capture_output=True, timeout=5)
                    plist.unlink(missing_ok=True)
                except Exception:
                    pass

    def _resolve_device_id(self):
        if SYSTEM_DEVICE_FILE.exists():
            try:
                import json
                state = json.loads(SYSTEM_DEVICE_FILE.read_text())
                if "device_id" in state:
                    return state["device_id"]
            except Exception:
                pass
        return load_device_id()

    def _deferred_setup(self, timer):
        timer.stop()
        if not self.token:
            self._run_setup()
        elif not self.device_id:
            self._do_device_naming()

    def _setup_menu(self):
        self.menu.clear()
        self.status_item = rumps.MenuItem("Status: Not connected", callback=None)
        self.menu.add(self.status_item)

        if self.token and self.device_id:
            self._build_authenticated_menu()
        else:
            self._build_unauthenticated_menu()

    def _build_authenticated_menu(self):
        self.menu.add(rumps.separator)
        self.menu.add(rumps.MenuItem("View latest plan", callback=self.view_plan))
        self.menu.add(rumps.MenuItem("Generate plan now", callback=self.generate_plan_now))
        self.menu.add(rumps.separator)

        autostart_label = "\u2705 Auto-start" if self._is_autostart_enabled() else "\u2b1c Auto-start"
        self.menu.add(rumps.MenuItem(autostart_label, callback=self._toggle_autostart))

        if self.tracking:
            self.menu.add(rumps.MenuItem("\u23f8 Pause tracking", callback=self.toggle_tracking))
        else:
            self.menu.add(rumps.MenuItem("\u25b6\ufe0f Start tracking", callback=self.toggle_tracking))

        self.menu.add(rumps.separator)
        self.menu.add(rumps.MenuItem("Logout", callback=self.logout))
        self.menu.add(rumps.MenuItem("Quit", callback=self.quit_app))

    def _build_unauthenticated_menu(self):
        self.menu.add(rumps.separator)
        self.menu.add(rumps.MenuItem("Setup (Login)", callback=self._run_setup))
        self.menu.add(rumps.separator)
        self.menu.add(rumps.MenuItem("Quit", callback=self.quit_app))

    def _is_autostart_enabled(self):
        plist_path = Path.home() / "Library" / "LaunchAgents" / f"{PLIST_LABEL}.plist"
        if plist_path.exists():
            return True
        return False

    def _toggle_autostart(self, _):
        plist_path = Path.home() / "Library" / "LaunchAgents" / f"{PLIST_LABEL}.plist"
        if plist_path.exists():
            subprocess.run(["launchctl", "unload", str(plist_path)], capture_output=True)
            plist_path.unlink(missing_ok=True)
        else:
            self._install_launchd_plist()
        self._setup_menu()

    def _install_launchd_plist(self):
        plist_path = Path.home() / "Library" / "LaunchAgents" / f"{PLIST_LABEL}.plist"
        SYSTEM_DIR.mkdir(parents=True, exist_ok=True)

        if getattr(sys, 'frozen', False):
            # Running as .app bundle: use open -a to launch
            app_path = Path(os.path.dirname(sys.executable)).parent.parent
            program_args = f"""        <string>/usr/bin/open</string>
        <string>-a</string>
        <string>{app_path}</string>"""
            working_dir = SYSTEM_DIR
            log_path = SYSTEM_DIR
        else:
            # Running from source: use python script
            agent_dir = Path(__file__).resolve().parent.parent
            main_py = agent_dir / "main.py"
            python = sys.executable
            program_args = f"""        <string>{python}</string>
        <string>{main_py}</string>
        <string>tray</string>
        <string>--autostart</string>"""
            working_dir = agent_dir
            log_path = agent_dir / "data"

        plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{PLIST_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
{program_args}
    </array>
    <key>WorkingDirectory</key>
    <string>{working_dir}</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>ThrottleInterval</key>
    <integer>5</integer>
    <key>StandardOutPath</key>
    <string>{log_path}/tray.log</string>
    <key>StandardErrorPath</key>
    <string>{log_path}/tray.err</string>
</dict>
</plist>"""

        plist_path.parent.mkdir(parents=True, exist_ok=True)
        plist_path.write_text(plist_content)
        subprocess.run(["launchctl", "load", str(plist_path)], capture_output=True)

    def _run_setup(self, _=None):
        resp = rumps.alert(
            title="ScreenPlan Setup",
            message="Welcome! Would you like to login?",
            ok="Login",
            cancel="Register on Web",
        )
        if resp == 1:
            self._do_login_flow()
        else:
            import webbrowser
            url = get_backend_url()
            if url:
                webbrowser.open(url)

    def _do_login_flow(self):
        email_window = rumps.Window(
            message="Enter your email address",
            title="ScreenPlan Login",
            default_text="",
            ok="Next",
            cancel="Cancel",
            dimensions=(340, 130),
        )
        resp = email_window.run()
        if resp.clicked == 0:
            return
        email = resp.text.strip()
        if not email:
            return

        pass_window = rumps.Window(
            message="Enter your password",
            title="ScreenPlan Login",
            default_text="",
            ok="Login",
            cancel="Cancel",
            dimensions=(340, 130),
            secure=True,
        )
        resp = pass_window.run()
        if resp.clicked == 0:
            return
        password = resp.text.strip()
        if not password:
            return

        try:
            auth_resp = login(email, password)
            if not auth_resp:
                rumps.alert(
                    title="Login Failed",
                    message="Check your credentials or network connection.",
                    ok="OK",
                )
                return
            save_token(auth_resp.access_token)
            self.token = auth_resp.access_token
            print(f"[setup] Login OK, user={auth_resp.display_name}", file=sys.stderr)
            self._do_device_naming()
            self._setup_menu()
            self._update_status()
        except Exception as e:
            rumps.alert(
                title="Error",
                message=str(e),
                ok="OK",
            )

    def _do_device_naming(self):
        hostname = socket.gethostname()
        window = rumps.Window(
            message="Name this device",
            title="ScreenPlan Setup",
            default_text=hostname,
            ok="Register",
            cancel="Cancel",
            dimensions=(340, 130),
        )
        resp = window.run()
        if resp.clicked == 0:
            return
        device_name = resp.text.strip() or hostname
        self._register_and_save(device_name)
        self._setup_menu()

    def _register_and_save(self, device_name):
        try:
            print(f"[setup] Registering device: {device_name}", file=sys.stderr)
            device_id = register_device(self.token, device_name, "macos")
            print(f"[setup] register_device returned: {device_id}", file=sys.stderr)
            if device_id:
                self.device_id = device_id
                save_device_identity(device_id)
                save_device_id(device_id)
            else:
                print("[setup] register_device returned None - check server", file=sys.stderr)
        except Exception as e:
            print(f"[setup] register exception: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
        self._setup_menu()
        self._update_status()

    def _update_status(self):
        backend_url = get_backend_url()
        if not backend_url:
            self.status_item.title = "Status: No server configured"
            self.title = "\U0001f4ca"
            return

        health = health_check()
        offline = get_queue_size()

        if not health:
            extra = f" (offline: {offline})" if offline else ""
            self.status_item.title = f"Status: Offline{extra}"
            self.title = "\U0001f4ca"
            return

        if not self.token:
            self.token = load_token()
        if not self.device_id:
            self.device_id = self._resolve_device_id()

        if self.token and self.device_id:
            extra = f" (offline: {offline})" if offline else ""
            self.status_item.title = f"Status: Connected{extra}"
            self.title = "\U0001f4ca"
        else:
            self.status_item.title = "Status: Online - Not logged in"
            self.title = "\U0001f4ca"

    def _try_flush_queue(self):
        if not self.token or not self.device_id:
            return
        if get_queue_size() > 0:
            flush_offline_queue(self.token, self.device_id)

    def _on_tick(self, _):
        self._update_status()
        self._try_flush_queue()

    def toggle_tracking(self, _):
        self.tracking = not self.tracking
        if self.tracking:
            self.tracker_thread = threading.Thread(target=self._tracker_loop, daemon=True)
            self.tracker_thread.start()
        self._setup_menu()

    def _tracker_loop(self):
        interval_seconds = 3 * 60
        token = load_token()
        device_id = load_device_id()
        t0 = time.monotonic()
        while self.tracking:
            t1 = time.monotonic()
            drift = t1 - t0 - interval_seconds
            if drift > interval_seconds * 2:
                print(f"[tracker] Sleep/wake detected (drift={drift:.0f}s)", file=sys.stderr)
            t0 = time.monotonic()
            try:
                entry = record_current_app()
                if entry is not None:
                    print(f"[{entry['time']}] {entry['app']} ({entry['category']})")
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
        self.status_item.title = "Status: Generating plan..."
        plan = generate_schedule(self.token, include_calendar=True)
        if plan:
            self.status_item.title = "Status: Plan generated"
        else:
            self.status_item.title = "Status: Generation failed"

    def view_plan(self, _):
        if not self.token:
            return
        plan = fetch_latest_schedule(self.token)
        if plan:
            rumps.alert("Latest Plan", plan[:2000])
        else:
            rumps.alert("No Plan", "No plan generated yet.")

    def logout(self, _):
        delete_token()
        self.token = None
        self.device_id = None
        self.tracking = False
        self._setup_menu()
        self._update_status()

    def quit_app(self, _):
        self.tracking = False
        rumps.quit_application()


def run_tray(auto_start_tracking=False):
    app = ScreenPlanTrayApp(auto_start_tracking=auto_start_tracking)
    app.run()
