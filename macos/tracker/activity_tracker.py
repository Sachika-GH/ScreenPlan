"""
activity_tracker.py - macOS foreground app tracker.
"""
from tracker import record_current_app, read_activity_log, run_tracker_loop, get_current_app_name, classify_app
activity_tracker = {
    "record": record_current_app,
    "read": read_activity_log,
    "daemon": run_tracker_loop,
    "app_name": get_current_app_name,
    "classify": classify_app,
}
