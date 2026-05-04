"""Windows auto-start management via registry."""

import os
import sys
import winreg


REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
REG_NAME = "ScreenPlanAgent"


def get_exe_path():
    """Get the path to the current executable or Python script."""
    if getattr(sys, 'frozen', False):
        return sys.executable
    return sys.executable + ' "' + os.path.abspath(sys.argv[0]) + '"'


def is_autostart_enabled():
    """Check if auto-start is currently enabled."""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_READ)
        value, _ = winreg.QueryValueEx(key, REG_NAME)
        winreg.CloseKey(key)
        return bool(value)
    except FileNotFoundError:
        return False


def enable_autostart(exe_path=None):
    """Enable auto-start on boot."""
    if exe_path is None:
        exe_path = get_exe_path()
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, REG_NAME, 0, winreg.REG_SZ, exe_path)
        winreg.CloseKey(key)
        return True
    except Exception:
        return False


def disable_autostart():
    """Disable auto-start on boot."""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_SET_VALUE)
        winreg.DeleteValue(key, REG_NAME)
        winreg.CloseKey(key)
        return True
    except FileNotFoundError:
        return True
    except Exception:
        return False
