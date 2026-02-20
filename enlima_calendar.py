#!/usr/bin/env python3
"""
Scrape EnLima agenda by day and output events_by_day.json for the calendar.
Fetches https://enlima.pe/calendario-cultural/dia/YYYY-MM-DD for full year 2026.
"""
import json
import re
import sys
from pathlib import Path

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "beautifulsoup4", "lxml"])
    import requests
    from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
}
BASE = "https://enlima.pe"
OUTPUT = Path(__file__).resolve().parent / "events_by_day.json"


def fetch_day(year, month, day):
    url = f"{BASE}/calendario-cultural/dia/{year}-{month:02d}-{day:02d}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=12)
        r.raise_for_status()
        return BeautifulSoup(r.text, "lxml")
    except Exception as e:
        print(f"  Error {url}: {e}", file=sys.stderr)
        return None


def parse_day_page(soup, date_key):
    events = []
    if not soup:
        return events
    # Table: Hora | TIPO | EVENTO | LUGAR | DISTRITO | PRECIO
    table = soup.select_one("table")
    if not table:
        return events
    rows = table.select("tr")
    for row in rows:
        cells = row.select("td")
        if len(cells) < 4:
            continue
        # Try to get link and text from event cell (often index 2). Table: Hora | TIPO | EVENTO | LUGAR | ...
        time_val = cells[0].get_text(strip=True) if len(cells) > 0 else ""
        if not time_val or not re.search(r"\d{1,2}:\d{2}", time_val):
            row_text = row.get_text(separator=" ", strip=True)
            tm = re.search(r"(\d{1,2}:\d{2}\s*(?:am|pm|hrs?\.?)?)", row_text, re.I)
            if tm:
                time_val = tm.group(1).strip()
        type_val = cells[1].get_text(strip=True) if len(cells) > 1 else ""
        event_cell = cells[2] if len(cells) > 2 else None
        venue = (cells[3].get_text(strip=True) if len(cells) > 3 else "").replace("Lime", "Lima")
        district = (cells[4].get_text(strip=True) if len(cells) > 4 else "").replace("Lime", "Lima")
        price = cells[5].get_text(strip=True) if len(cells) > 5 else ""
        title = ""
        url = ""
        if event_cell:
            a = event_cell.select_one("a[href]")
            if a:
                url = a.get("href", "")
                if url and not url.startswith("http"):
                    url = BASE + url
                title = a.get_text(strip=True)
            else:
                title = event_cell.get_text(strip=True)
        if not title:
            continue
        events.append({
            "time": time_val,
            "type": type_val,
            "title": title,
            "url": url,
            "venue": venue,
            "district": district,
            "price": price,
        })
    return events


MONTH_ES = ("", "Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic")


def event_key(ev):
    """Unique key for deduplication: same title + url = same event."""
    return (ev.get("title", "").strip(), ev.get("url", "").strip())


def format_date_short(date_key):
    """e.g. 2026-02-15 -> '15 Ene' (day + month)."""
    try:
        y, m, d = date_key.split("-")
        return f"{int(d)} {MONTH_ES[int(m)]}"
    except Exception:
        return date_key


def dedupe_repeating_events(events_by_day):
    """
    If the same event (same title+url) appears on multiple days, show it only on
    the first day and add a 'schedule' note (date range).
    """
    # Collect (date_key, event) and group by event_key
    by_event = {}
    for date_key in sorted(events_by_day.keys()):
        for ev in events_by_day[date_key]:
            k = event_key(ev)
            if k not in by_event:
                by_event[k] = []
            by_event[k].append((date_key, dict(ev)))

    # For each event that appears on 2+ days, keep only first day and set schedule
    for k, date_ev_list in by_event.items():
        if len(date_ev_list) < 2:
            continue
        dates = sorted(d[0] for d in date_ev_list)
        first_date = dates[0]
        last_date = dates[-1]
        # Use the event from the first day
        ev = date_ev_list[0][1]
        ev["schedule"] = f"Del {format_date_short(first_date)} al {format_date_short(last_date)}"
        # Remove this event from every day
        for date_key in events_by_day:
            events_by_day[date_key] = [
                e for e in events_by_day[date_key]
                if event_key(e) != k
            ]
        # Add it only on the first day
        events_by_day[first_date].append(ev)

    return events_by_day


def is_enlima_event(ev):
    """True if this event came from EnLima (so we can replace only those when re-scraping)."""
    url = (ev.get("url") or "").strip()
    return "enlima.pe" in url


def main():
    # Start from existing calendar if present, so we don't remove Eventbrite/Teleticket events
    if OUTPUT.exists():
        with open(OUTPUT, "r", encoding="utf-8") as f:
            events_by_day = json.load(f)
    else:
        events_by_day = {}

    # 2026: Feb (29 days) through Dec (31 days)
    MONTH_DAYS = [(2, 29), (3, 31), (4, 30), (5, 31), (6, 30), (7, 31), (8, 31), (9, 30), (10, 31), (11, 30), (12, 31)]
    for month, last_day in MONTH_DAYS:
        for day in range(1, last_day + 1):
            date_key = f"2026-{month:02d}-{day:02d}"
            if date_key not in events_by_day:
                events_by_day[date_key] = []
            events_by_day[date_key] = [e for e in events_by_day[date_key] if not is_enlima_event(e)]
            soup = fetch_day(2026, month, day)
            new_events = parse_day_page(soup, date_key)
            events_by_day[date_key].extend(new_events)
            if new_events:
                print(f"  {date_key}: {len(new_events)} EnLima events")

    print("  Deduplicating repeating events...")
    events_by_day = dedupe_repeating_events(events_by_day)

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(events_by_day, f, ensure_ascii=False, indent=2)
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
