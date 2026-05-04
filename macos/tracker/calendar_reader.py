"""
calendar_reader.py
Reads macOS Calendar events using JXA (JavaScript for Automation).
"""
import json
import subprocess
import sys
from datetime import date
from typing import Optional, Any


def run_jxa(script: str, timeout: int = 60) -> tuple[int, str, str]:
    proc = subprocess.run(
        ["osascript", "-l", "JavaScript", "-e", script],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def read_calendar_events(target_date: Optional[date] = None) -> list[dict[str, Any]]:
    if target_date is None:
        target_date = date.today()

    date_str = target_date.isoformat()
    safe_date = date_str.replace("`", "").replace("$", "")

    jxa_script = f'''
function pad(n) {{
    return n < 10 ? "0" + n : String(n);
}}

var Calendar = Application("Calendar");
var startDate = new Date("{safe_date}T00:00:00");
var endDate = new Date("{safe_date}T23:59:59");

var results = [];
var cals = Calendar.calendars();

for (var i = 0; i < cals.length; i++) {{
    var cal = cals[i];
    try {{
        var calName = cal.name();
        var calEvents = cal.events.whose({{
            _and: [
                {{ _greaterThanEquals: {{ startDate: startDate }} }},
                {{ _lessThanEquals: {{ startDate: endDate }} }}
            ]
        }});
        var evts = calEvents();
        for (var j = 0; j < evts.length; j++) {{
            var evt = evts[j];
            try {{
                var title = evt.summary() || "(无标题)";
                var evtStart = evt.startDate();
                var evtEnd = evt.endDate();
                var allDay = evt.alldayEvent();
                var location = evt.location() || "";
                var notes = evt.description() || "";

                var startH = pad(evtStart.getHours());
                var startM = pad(evtStart.getMinutes());
                var endH = pad(evtEnd.getHours());
                var endM = pad(evtEnd.getMinutes());

                results.push(
                    title + "|||" +
                    startH + ":" + startM + "|||" +
                    endH + ":" + endM + "|||" +
                    (allDay ? "true" : "false") + "|||" +
                    calName + "|||" +
                    location + "|||" +
                    notes + "|||"
                );
            }} catch (e2) {{ }}
        }}
    }} catch (e1) {{ }}
}}

results.join("\\n");
'''

    returncode, stdout, stderr = run_jxa(jxa_script, timeout=90)

    if returncode != 0:
        print(f"[calendar] JXA failed: {stderr}", file=sys.stderr)
        return []

    if not stdout:
        return []

    events = []
    for line in stdout.split("\n"):
        line = line.strip()
        if not line:
            continue
        parts = line.split("|||")
        if len(parts) < 7:
            continue
        events.append({
            "title": parts[0],
            "start_time": parts[1],
            "end_time": parts[2],
            "is_all_day": parts[3].lower() == "true",
            "calendar": parts[4],
            "location": parts[5],
            "notes": parts[6],
        })

    events.sort(key=lambda e: e["start_time"])
    return events


def format_calendar_for_prompt(events: list[dict[str, Any]]) -> str:
    if not events:
        return "（今日无日历安排）"

    lines = []
    for e in events:
        time_range = f"{e['start_time']}-{e['end_time']}"
        if e["is_all_day"]:
            time_range = "全天"
        location_info = f" @{e['location']}" if e["location"] else ""
        lines.append(f"- {time_range} | {e['title']}{location_info} [{e['calendar']}]")
    return "\n".join(lines)
