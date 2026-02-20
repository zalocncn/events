#!/usr/bin/env python3
"""
Run all calendar scrapers in order to refresh events_by_day.json.
Use this for hourly updates: new events from EnLima, Eventbrite, and Teleticket
are merged in; existing events from other sources are kept.

Usage:
  python3 update_calendar.py           # Full run (EnLima → Eventbrite → Teleticket)
  SKIP_TELETICKET_FETCH=1 python3 update_calendar.py   # Skip per-event time fetch (faster, e.g. in CI)
"""
import os
import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
EVENTS_FILE = PROJECT_DIR / "events_by_day.json"

SCRIPTS = [
    "enlima_calendar.py",
    "eventbrite_calendar.py",
    "teleticket_calendar.py",
]


def main():
    # Ensure we have a base file so Eventbrite/Teleticket can merge (EnLima creates/merges it)
    if not EVENTS_FILE.exists():
        with open(EVENTS_FILE, "w", encoding="utf-8") as f:
            f.write("{}")
    for name in SCRIPTS:
        script = PROJECT_DIR / name
        if not script.exists():
            print(f"  Skip (not found): {name}")
            continue
        print(f"\n  Running {name} ...")
        env = os.environ.copy()
        # In CI or when set, Teleticket skips per-event page fetch (saves time; events still added, times may be empty)
        if os.environ.get("SKIP_TELETICKET_FETCH") and "teleticket" in name:
            env["SKIP_TELETICKET_FETCH"] = "1"
        ret = subprocess.run(
            [sys.executable, str(script)],
            cwd=PROJECT_DIR,
            env=env,
        )
        if ret.returncode != 0:
            print(f"  Warning: {name} exited with {ret.returncode}")
    print("\n  Calendar update finished.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
