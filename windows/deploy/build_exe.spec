# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path
import os

# Resolve absolute paths relative to this spec file
_SPEC_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
_PROJ_DIR = _SPEC_DIR.parent  # windows/

block_cipher = None

a = Analysis(
    [str(_PROJ_DIR / 'main.py')],
    pathex=[str(_PROJ_DIR)],
    binaries=[],
    datas=[
        (str(_PROJ_DIR / 'config.json'), '.'),
    ],
    hiddenimports=[
        'keyring.backends.Windows',
        'pystray._win32',
        'PIL._tkinter_finder',
        'win32gui',
        'win32process',
        'winreg',
        'psutil',
        'tkinter',
        'tkinter.simpledialog',
        'tkinter.messagebox',
        'network.auth_manager',
        'network.gateway',
        'network.sync_client',
        'network.autostart',
        'ui.tray_app',
        'ui.setup_window',
        'ui',
        'tracker',
        'protocol_models',
        'requests',
        'pydantic',
        'jwt',
        'email_validator',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter.test', 'test', 'unittest', 'pydoc'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ScreenPlan',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No console window - tray app only
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
