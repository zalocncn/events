#!/usr/bin/env python3
"""
Fetch Teleticket events and merge them into events_by_day.json.
Run after enlima + eventbrite:  python3 enlima_calendar.py && python3 eventbrite_calendar.py && python3 teleticket_calendar.py
"""
import json
import os
import re
import time
from pathlib import Path

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    import subprocess
    import sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "beautifulsoup4", "lxml"])
    import requests
    from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
}
TELETICKET_URL = "https://teleticket.com.pe/todos"
EVENTS_FILE = Path(__file__).resolve().parent / "events_by_day.json"

MES_A_NUM = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "setiembre": 9, "septiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}

MES_LABEL = ["", "Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


def fetch_teleticket():
    try:
        r = requests.get(TELETICKET_URL, headers=HEADERS, timeout=15)
        r.raise_for_status()
        return BeautifulSoup(r.text, "lxml")
    except Exception as e:
        print(f"  Error fetching Teleticket: {e}", file=__import__("sys").stderr)
        return None


def parse_date_range(date_str):
    """Parse '20 de febrero 2026 - 04 de marzo 2026' or '20 de febrero 2026'
    Returns (first_date_key, last_date_key) or (None, None)."""
    date_str = (date_str or "").strip().lower()

    # Find all date occurrences: "DD de MES YYYY"
    dates = re.findall(
        r"(\d{1,2})\s+de\s+(enero|febrero|marzo|abril|mayo|junio|julio|agosto|"
        r"setiembre|septiembre|octubre|noviembre|diciembre)\s+(\d{4})",
        date_str
    )
    if not dates:
        return None, None

    keys = []
    for day_s, month_name, year_s in dates:
        month = MES_A_NUM.get(month_name)
        if not month:
            continue
        keys.append(f"{int(year_s)}-{month:02d}-{int(day_s):02d}")

    if not keys:
        return None, None
    return keys[0], keys[-1]


def fetch_event_time(event_url):
    """Fetch event detail page and extract time. Returns '' if not found."""
    try:
        r = requests.get(event_url, headers=HEADERS, timeout=12)
        r.raise_for_status()
        text = r.text

        # "26-02-2026 20:00 Hrs." or "20:00 Hrs."
        m = re.search(r"(\d{1,2}:\d{2})\s*[Hh]rs?\.?", text)
        if m:
            return _normalize_time(m.group(1))
        # "Hora de inicio: ... 8:00 p.m." or "a las 8:00 p.m."
        m = re.search(r"(?:inicio|comenzar|comienza|a las|las)\s+(\d{1,2}:\d{2}\s*[ap]\.?m\.?)", text, re.I)
        if m:
            return _normalize_time(m.group(1))
        # "jue. 26 Febrero 20:00"
        m = re.search(r"(?:lun|mar|mi[eé]|jue|vie|s[aá]b|dom)\.?\s+\d{1,2}\s+\w+\s+(\d{1,2}:\d{2})", text, re.I)
        if m:
            return _normalize_time(m.group(1))
        # DD-MM-YYYY HH:MM or DD/MM/YYYY HH:MM
        m = re.search(r"\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\s+(\d{1,2}:\d{2})", text)
        if m:
            return _normalize_time(m.group(1))
        # 12h format: 8:00 pm, 9:30 am
        m = re.search(r"\b(\d{1,2}:\d{2}\s*[ap]\.?m\.?)\b", text, re.I)
        if m:
            return _normalize_time(m.group(1))
        # 24h format near "horas" or time context
        m = re.search(r"\b([0-2]?\d:\d{2})\s*(?:[Hh]rs?|[Hh]ora)?", text)
        if m:
            raw = m.group(1)
            if re.match(r"^([0-2]?\d):(\d{2})$", raw):
                h, mi = int(raw.split(":")[0]), raw.split(":")[1]
                if 0 <= h <= 23 and 0 <= int(mi) <= 59:
                    return _normalize_time(raw)
        # Fallback: any HH:MM (12h)
        m = re.search(r"\b(0?[1-9]|1[0-2]):(\d{2})\s*([ap]\.?m\.?)?", text, re.I)
        if m:
            return _normalize_time(m.group(0).strip())
    except Exception:
        pass
    return ""


def _normalize_time(t):
    """Normalize to 12-hour AM/PM display, e.g. '8:00 pm', '10:00 am'."""
    t = (t or "").strip()
    m = re.match(r"(\d{1,2}):(\d{2})\s*([ap]\.?m\.?)?", t, re.I)
    if not m:
        return t
    h, min_val, ampm = int(m.group(1)), m.group(2), (m.group(3) or "").strip().lower()
    if ampm:
        return f"{h}:{min_val} {ampm.replace('.', '')}".replace("am", "am").replace("pm", "pm")
    # 24-hour to 12-hour
    if h == 0:
        return f"12:{min_val} am"
    if h < 12:
        return f"{h}:{min_val} am"
    if h == 12:
        return f"12:{min_val} pm"
    return f"{h - 12}:{min_val} pm"


def scrape_teleticket_events(soup):
    """
    FIX: Use <article id="event_N"> selectors to target individual event cards.
    Each card has: <h3> (title), <p class="fecha"> (date), <p class="descripcion"> (category),
    <img class="img--evento"> (image), and a wrapper <a href="..."> (link).
    """
    events_with_dates = []
    if not soup:
        return events_with_dates

    # Target the specific event article cards
    cards = soup.select('article[id^="event_"]')
    if not cards:
        cards = soup.select('.listado--eventos article')
    if not cards:
        cards = soup.select('article.col-4')

    for card in cards:
        try:
            link = card.select_one('a[href]')
            if not link:
                continue

            href = (link.get("href") or "").strip()
            if not href or href == "#":
                continue
            if href.startswith("/"):
                href = "https://teleticket.com.pe" + href

            # Skip non-event URLs
            if any(s in href for s in ("/Cliente/", "/Account/", "/puntosventa",
                                       "/Register", "/SignIn", "/SignOut")):
                continue

            # Title from <h3>
            title_el = card.select_one('h3')
            title = title_el.get_text(strip=True) if title_el else ""
            if not title or len(title) < 3:
                continue
            # Skip navigation items
            if title.upper() in ("VER MÁS", "VER TODOS", "VER TODO"):
                continue

            # Date from <p class="fecha">
            fecha_el = card.select_one('p.fecha')
            date_text = fecha_el.get_text(strip=True) if fecha_el else ""

            first_key, last_key = parse_date_range(date_text)
            if not first_key:
                continue
            # Only include 2026
            if not first_key.startswith("2026-"):
                continue

            # Category from <p class="descripcion">
            desc_el = card.select_one('p.descripcion')
            desc = desc_el.get_text(strip=True) if desc_el else ""
            # Extract category after the slash: "WWW.TELETICKET.COM.PE - WEB / Humor"
            cat = ""
            if "/" in desc:
                cat = desc.split("/")[-1].strip()

            # Schedule label for multi-day events
            schedule = None
            if first_key != last_key:
                try:
                    d1 = first_key.split("-")
                    d2 = last_key.split("-")
                    schedule = (
                        f"Del {int(d1[2])} {MES_LABEL[int(d1[1])]} "
                        f"al {int(d2[2])} {MES_LABEL[int(d2[1])]}"
                    )
                except Exception:
                    schedule = f"Del {first_key} al {last_key}"

            ev = {
                "time": "",  # Will be filled by fetch_event_time()
                "type": cat or "Teleticket",
                "title": title[:120],
                "url": href,
                "venue": "",
                "district": "Lima",
                "price": "",
                "source": "Teleticket",
            }
            if schedule:
                ev["schedule"] = schedule

            events_with_dates.append((first_key, ev))
        except Exception:
            continue

    return events_with_dates


def main():
    print("  Fetching Teleticket...")
    soup = fetch_teleticket()
    events_with_dates = scrape_teleticket_events(soup)

    # Deduplicate by title+url
    seen = set()
    deduped = []
    for date_key, ev in events_with_dates:
        k = (ev["title"][:60], ev["url"])
        if k in seen:
            continue
        seen.add(k)
        deduped.append((date_key, ev))
    events_with_dates = deduped
    print(f"  Found {len(events_with_dates)} Teleticket events (2026)")

    # Fetch time from each event detail page unless SKIP_TELETICKET_FETCH is set
    if not os.environ.get("SKIP_TELETICKET_FETCH"):
        fetched = 0
        for i, (date_key, ev) in enumerate(events_with_dates):
            if not ev.get("url"):
                continue
            if i > 0:
                time.sleep(0.35)
            t = fetch_event_time(ev["url"])
            if t:
                ev["time"] = t
                fetched += 1
            if (i + 1) % 10 == 0:
                print(f"    Fetched {i + 1}/{len(events_with_dates)} detail pages...")
        print(f"  Got time for {fetched}/{len(events_with_dates)} Teleticket events")
    else:
        print("  Skipping per-event time fetch (SKIP_TELETICKET_FETCH=1)")

    if not EVENTS_FILE.exists():
        print(f"  {EVENTS_FILE} not found. Run enlima_calendar.py first.")
        return

    with open(EVENTS_FILE, "r", encoding="utf-8") as f:
        events_by_day = json.load(f)

    # Remove existing Teleticket events to avoid duplicates
    def is_teleticket_event(e):
        u = e.get("url") or ""
        return "teleticket.com.pe" in u

    for date_key in list(events_by_day.keys()):
        events_by_day[date_key] = [e for e in events_by_day[date_key] if not is_teleticket_event(e)]

    added = 0
    for date_key, ev in events_with_dates:
        if date_key not in events_by_day:
            events_by_day[date_key] = []
        events_by_day[date_key].append(ev)
        added += 1

    with open(EVENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(events_by_day, f, ensure_ascii=False, indent=2)
    print(f"  Merged {added} Teleticket events into calendar. Wrote {EVENTS_FILE}")


if __name__ == "__main__":
    main()
