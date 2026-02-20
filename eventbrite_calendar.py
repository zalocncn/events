#!/usr/bin/env python3
"""
Fetch Eventbrite Miraflores events and merge them into events_by_day.json
so they appear on the calendar alongside EnLima events.
Run after enlima_calendar.py:  python3 enlima_calendar.py && python3 eventbrite_calendar.py
"""
import json
import re
import sys
from datetime import datetime
from pathlib import Path

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    subprocess = __import__("subprocess")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "beautifulsoup4", "lxml"])
    import requests
    from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
}
EVENTBRITE_URL = "https://www.eventbrite.com.pe/d/peru--miraflores/events/"
EVENTS_FILE = Path(__file__).resolve().parent / "events_by_day.json"

# Month name to number (English from Eventbrite)
MONTH_NUM = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
             "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}


def fetch_eventbrite():
    try:
        r = requests.get(EVENTBRITE_URL, headers=HEADERS, timeout=15)
        r.raise_for_status()
        return BeautifulSoup(r.text, "lxml")
    except Exception as e:
        print(f"  Error fetching Eventbrite: {e}", file=sys.stderr)
        return None


def parse_date_and_time(date_text, default_year=2026):
    """Parse 'Thu, Feb 26, 7:00 PM' or 'Fri, Mar 6, 7:00 PM' -> (date_key, time_str)."""
    date_text = (date_text or "").strip()
    time_str = ""
    # Match: "Thu, Feb 26, 7:00 PM" or "Sat, Mar 7, 8:00 AM"
    m = re.search(r"(Mon|Tue|Wed|Thu|Fri|Sat|Sun),\s*(\w{3})\s+(\d{1,2}),\s*(\d{1,2}:\d{2}\s*[AP]M)", date_text, re.I)
    if m:
        _, month_str, day_str, time_str = m.groups()
        month = MONTH_NUM.get(month_str[:3].title())
        if month:
            day = int(day_str)
            date_key = f"{default_year}-{month:02d}-{day:02d}"
            return date_key, time_str.strip()
    # "mañana a las 09:00" -> tomorrow
    if "mañana" in date_text.lower():
        from datetime import timedelta
        t = datetime.now() + timedelta(days=1)
        return t.strftime("%Y-%m-%d"), re.sub(r".*?(\d{1,2}:\d{2}).*", r"\1", date_text) or ""
    return None, time_str


def scrape_eventbrite_events(soup):
    events_with_dates = []
    seen_urls = set()
    if not soup:
        return events_with_dates
    for link in soup.select('a[href*="/e/"]'):
        try:
            url = link.get("href", "")
            if not url or url in seen_urls:
                continue
            if not url.startswith("http"):
                url = "https://www.eventbrite.com.pe" + url
            seen_urls.add(url)
            card_text = ""
            parent = link.parent
            for _ in range(8):
                if not parent:
                    break
                card_text = parent.get_text(separator=" ", strip=True)
                if len(card_text) > 50:
                    break
                parent = getattr(parent, "parent", None)
            if not card_text:
                continue
            date_match = re.search(
                r"(Mon|Tue|Wed|Thu|Fri|Sat|Sun),\s*(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2}),\s*(\d{1,2}:\d{2}\s*[AP]M)",
                card_text, re.I
            )
            time_str = ""
            if date_match:
                time_str = date_match.group(4).strip() if date_match.lastindex >= 4 else ""
            if not time_str:
                tm = re.search(r"(\d{1,2}:\d{2}\s*[AP]M)", card_text, re.I)
                if tm:
                    time_str = tm.group(1).strip()
            if not time_str:
                tm = re.search(r"(\d{1,2}:\d{2})\s*(?:hrs?|h|AM|PM|am|pm)?", card_text)
                if tm:
                    time_str = tm.group(1).strip()
            date_match = re.search(
                r"(Mon|Tue|Wed|Thu|Fri|Sat|Sun),\s*(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2})",
                card_text, re.I
            )
            if date_match:
                _, month_str, day_str = date_match.groups()
                month = MONTH_NUM.get(month_str[:3].title())
                if month:
                    day = int(day_str)
                    date_key = f"2026-{month:02d}-{day:02d}"
                    title = link.get_text(strip=True)
                    if not title:
                        before = card_text[:date_match.start()].strip()
                        before = re.sub(r"^.*?(La venta se termina pronto|Comprobar|Guarda).*?", "", before, flags=re.I).strip()
                        before = re.sub(r"\s+", " ", before).strip()
                        title = before[-80:] if len(before) > 10 else before or "Event"
                    if len(title) < 3:
                        continue
                    if title.startswith("La venta "):
                        continue
                    loc_match = re.search(r"(?:PM|AM)\s+([A-Za-z0-9].*?)(?:\s+Comprobar|\s+Guarda|$)", card_text)
                    location = (loc_match.group(1).strip() if loc_match else "Miraflores").replace("Lime", "Lima")
                    if len(location) > 80:
                        location = "Miraflores"
                    ev = {
                        "time": time_str.strip() if time_str else "",
                        "type": "Eventbrite",
                        "title": title[:120],
                        "url": url,
                        "venue": location,
                        "district": "Miraflores",
                        "price": "",
                        "source": "Eventbrite",
                    }
                    events_with_dates.append((date_key, ev))
                    continue
            if "mañana" in card_text.lower():
                from datetime import timedelta
                t = datetime.now() + timedelta(days=1)
                date_key = t.strftime("%Y-%m-%d")
                time_str = ""
                tm = re.search(r"(\d{1,2}:\d{2})", card_text)
                if tm:
                    time_str = tm.group(1)
                title = link.get_text(strip=True) or card_text[:60].strip()
                if len(title) < 2:
                    continue
                ev = {
                    "time": time_str,
                    "type": "Eventbrite",
                    "title": title[:120],
                    "url": url,
                    "venue": "Miraflores",
                    "district": "Miraflores",
                    "price": "",
                    "source": "Eventbrite",
                }
                events_with_dates.append((date_key, ev))
        except Exception:
            continue
    return events_with_dates


def main():
    print("  Fetching Eventbrite (Miraflores)...")
    soup = fetch_eventbrite()
    events_with_dates = scrape_eventbrite_events(soup)
    print(f"  Found {len(events_with_dates)} Eventbrite events with dates")

    if not Path(EVENTS_FILE).exists():
        print(f"  {EVENTS_FILE} not found. Run enlima_calendar.py first.")
        return

    with open(EVENTS_FILE, "r", encoding="utf-8") as f:
        events_by_day = json.load(f)

    # Remove existing Eventbrite events so we don't duplicate when re-running
    for date_key in list(events_by_day.keys()):
        if date_key.startswith("2026-"):
            events_by_day[date_key] = [e for e in events_by_day[date_key] if "eventbrite" not in (e.get("url") or "")]
    added = 0
    for date_key, ev in events_with_dates:
        if not date_key.startswith("2026-"):
            continue
        if date_key not in events_by_day:
            events_by_day[date_key] = []
        events_by_day[date_key].append(ev)
        added += 1

    with open(EVENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(events_by_day, f, ensure_ascii=False, indent=2)
    print(f"  Merged {added} Eventbrite events into calendar. Wrote {EVENTS_FILE}")


if __name__ == "__main__":
    main()
