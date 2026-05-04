"""
Build macOS .app bundle using py2app.
Usage: python build_app.py
"""
from setuptools import setup

APP = ['../main.py']
DATA_FILES = [
    ('', ['../config.json']),
]
OPTIONS = {
    'argv_emulation': False,
    'plist': {
        'CFBundleName': 'ScreenPlan',
        'CFBundleDisplayName': 'ScreenPlan',
        'CFBundleIdentifier': 'com.screenplan.agent',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'LSUIElement': True,
    },
    'packages': ['rumps', 'requests', 'pydantic', 'PyObjC'],
    'includes': ['email_validator'],
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
