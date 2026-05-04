"""
note_writer.py
Writes daily plan to macOS Notes app using AppleScript.
Based on the original fucktheworld project.
"""
import subprocess
import sys
from datetime import date
from typing import Optional


def escape_for_applescript(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def build_body_html(text: str) -> str:
    """Convert markdown plan text to HTML for Notes.app."""
    lines = text.split("\n")
    html_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("### "):
            html_lines.append(f"<h2>{stripped[4:]}</h2>")
        elif stripped.startswith("## "):
            html_lines.append(f"<h2>{stripped[3:]}</h2>")
        elif stripped == "---":
            html_lines.append("<hr>")
        elif stripped.startswith("> "):
            html_lines.append(f"<blockquote>{stripped[2:]}</blockquote>")
        elif stripped.startswith("- [ ]"):
            html_lines.append(f"<div>☐ {stripped[5:]}</div>")
        elif stripped.startswith("- "):
            html_lines.append(f"<div>{stripped[2:]}</div>")
        elif stripped == "":
            html_lines.append("<br>")
        else:
            html_lines.append(f"<div>{line}</div>")

    escaped = escape_for_applescript("\n".join(html_lines))
    return f'"{escaped}"'


def write_to_notes(title: str, body: str) -> bool:
    escaped_body = build_body_html(body)
    applescript = f'''
    tell application "Notes"
        activate
        delay 0.5
        set newNote to make new note with properties {{name:"{title}", body:{escaped_body}}}
        return name of newNote
    end tell
    '''

    try:
        proc = subprocess.run(
            ["osascript", "-e", applescript],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode == 0:
            print(f"[notes] Created: {proc.stdout.strip()}")
            return True
        else:
            print(f"[notes] Error: {proc.stderr}", file=sys.stderr)
            return False
    except Exception as e:
        print(f"[notes] Exception: {e}", file=sys.stderr)
        return False


def create_daily_plan_note(plan_text: str, target_date: Optional[date] = None) -> bool:
    if target_date is None:
        target_date = date.today()

    date_display = target_date.strftime("%Y-%m-%d")
    weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    weekday = weekday_names[target_date.weekday()]
    title = f"每日计划-{date_display} {weekday}"

    return write_to_notes(title, plan_text)
