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


def fetch_teleticket():
    try:
        r = requests.get(TELETICKET_URL, headers=HEADERS, timeout=15)
        r.raise_for_status()
        return BeautifulSoup(r.text, "lxml")
    except Exception as e:
        print(f"  Error fetching Teleticket: {e}", file=__import__("sys").stderr)
        return None


def parse_spanish_date(date_str):
    """Parse '20 de febrero 2026' or '01 de marzo 2026' -> (date_key,). Returns None if not in Feb-Mar 2026."""
    date_str = (date_str or "").strip().lower()
    m = re.search(r"(\d{1,2})\s+de\s+(enero|febrero|marzo|abril|mayo|junio|julio|agosto|setiembre|septiembre|octubre|noviembre|diciembre)\s+(\d{4})", date_str)
    if not m:
        return None
    day, month_name, year = int(m.group(1)), m.group(2), int(m.group(3))
    month = MES_A_NUM.get(month_name)
    if not month or year != 2026:
        return None
    return f"{year}-{month:02d}-{day:02d}"


def parse_date_range(date_str):
    """Parse '21 de febrero 2026 al 01 de marzo 2026' -> (first_key, last_key) or single '21 de febrero 2026' -> (key, key)."""
    date_str = (date_str or "").strip()
    first = re.search(r"(\d{1,2})\s+de\s+(enero|febrero|marzo|abril|mayo|junio|julio|agosto|setiembre|septiembre|octubre|noviembre|diciembre)\s+(\d{4})", date_str, re.I)
    if not first:
        return None, None
    day1, mes1, year1 = int(first.group(1)), MES_A_NUM.get(first.group(2).lower()), int(first.group(3))
    if not mes1:
        return None, None
    first_key = f"{year1}-{mes1:02d}-{day1:02d}"
    al = re.search(r"\s+al\s+(\d{1,2})\s+de\s+(enero|febrero|marzo|abril|mayo|junio|julio|agosto|setiembre|septiembre|octubre|noviembre|diciembre)\s+(\d{4})", date_str, re.I)
    if not al:
        return first_key, first_key
    day2, mes2, year2 = int(al.group(1)), MES_A_NUM.get(al.group(2).lower()), int(al.group(3))
    if not mes2:
        return first_key, first_key
    last_key = f"{year2}-{mes2:02d}-{day2:02d}"
    return first_key, last_key


def fetch_event_time(event_url):
    """Fetch event detail page and extract time (e.g. '20:00 Hrs.', '8:00 p.m.'). Returns '' if not found."""
    try:
        r = requests.get(event_url, headers=HEADERS, timeout=12)
        r.raise_for_status()
        text = r.text
        # "26-02-2026 20:00 Hrs." or "20:00 Hrs." (24h or 12h)
        m = re.search(r"(\d{1,2}:\d{2})\s*[Hh]rs?\.?", text)
        if m:
            return _normalize_time(m.group(1))
        # "Hora de inicio: ... 8:00 p.m." or "comenzar a las 8:00 p.m." or "a las 8:00 p.m."
        m = re.search(r"(?:inicio|comenzar|comienza|a las|las)\s+(\d{1,2}:\d{2}\s*[ap]\.?m\.?)", text, re.I)
        if m:
            return _normalize_time(m.group(1))
        # "jue. 26 Febrero 20:00" or "26 Febrero 20:00"
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
        # 24h format: 20:00, 09:00 (near "horas" or after date-like text)
        m = re.search(r"\b([0-2]?\d:\d{2})\s*(?:[Hh]rs?|[Hh]ora)?", text)
        if m:
            raw = m.group(1)
            if re.match(r"^([0-2]?\d):(\d{2})$", raw):
                h, mi = int(raw.split(":")[0]), raw.split(":")[1]
                if 0 <= h <= 23 and 0 <= int(mi) <= 59:
                    return _normalize_time(raw)
        # Fallback: any HH:MM (1-12 for 12h, or 0-23 for 24h)
        m = re.search(r"\b(0?[1-9]|1[0-2]):(\d{2})\s*([ap]\.?m\.?)?", text, re.I)
        if m:
            return _normalize_time(m.group(0).strip())
    except Exception:
        pass
    return ""


def _normalize_time(t):
    """Normalize to 12-hour AM/PM display form, e.g. '8:00 pm', '10:00 am'."""
    t = (t or "").strip()
    m = re.match(r"(\d{1,2}):(\d{2})\s*([ap]\.?m\.?)?", t, re.I)
    if not m:
        return t
    h, min_val, ampm = int(m.group(1)), m.group(2), (m.group(3) or "").strip().lower()
    if ampm:
        return f"{h}:{min_val} {ampm.replace('.', '')}".replace("am", "am").replace("pm", "pm")
    # 24-hour to 12-hour AM/PM
    if h == 0:
        return f"12:{min_val} am"
    if h < 12:
        return f"{h}:{min_val} am"
    if h == 12:
        return f"12:{min_val} pm"
    return f"{h - 12}:{min_val} pm"


def scrape_teleticket_events(soup):
    events_with_dates = []
    if not soup:
        return events_with_dates
    skip_paths = ("/Cliente/", "/Account/", "/conciertos", "/deportes", "/teatro", "/entretenimiento", "/otros", "/puntosventa", "/Register", "/SignIn", "/SignOut", "/MisOrdenes", "/MisETickets")
    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if not href or href == "#":
            continue
        if href.startswith("/"):
            href = "https://teleticket.com.pe" + href
        if "teleticket.com.pe" not in href:
            continue
        if any(s in href for s in skip_paths):
            continue
        if href.rstrip("/").endswith("/todos") or "/todos" in href.split("?")[0]:
            continue
        card_text = a.get_text(separator=" ", strip=True)
        parent = a.parent
        for _ in range(10):
            if not parent:
                break
            full = parent.get_text(separator=" ", strip=True)
            if len(full) > 30 and ("de febrero" in full or "de marzo" in full or "de enero" in full):
                card_text = full
                break
            parent = getattr(parent, "parent", None)
        first_key, last_key = parse_date_range(card_text)
        if not first_key:
            continue
        if not (first_key.startswith("2026-02") or first_key.startswith("2026-03")):
            continue
        title = a.get_text(strip=True)
        if not title or len(title) < 3:
            title = card_text[:80].strip()
        if len(title) < 2:
            continue
        if " / " in title:
            title = title.split(" / ")[0].strip()
        if len(title) > 100:
            title = title[:97] + "..."
        schedule = None
        if first_key != last_key:
            from datetime import datetime
            try:
                d1 = first_key.split("-")
                d2 = last_key.split("-")
                schedule = f"Del {int(d1[2])} {['','Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic'][int(d1[1])]} al {int(d2[2])} {['','Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic'][int(d2[1])]}"
            except Exception:
                schedule = f"Del {first_key} al {last_key}"
        ev = {
            "time": "",
            "type": "Teleticket",
            "title": title,
            "url": href if href.startswith("http") else "https://teleticket.com.pe" + href,
            "venue": "",
            "district": "Lima",
            "price": "",
            "source": "Teleticket",
        }
        if schedule:
            ev["schedule"] = schedule
        events_with_dates.append((first_key, ev))
    return events_with_dates


def main():
    print("  Fetching Teleticket...")
    soup = fetch_teleticket()
    events_with_dates = scrape_teleticket_events(soup)
    seen = set()
    deduped = []
    for date_key, ev in events_with_dates:
        k = (ev["title"][:60], ev["url"])
        if k in seen:
            continue
        seen.add(k)
        deduped.append((date_key, ev))
    events_with_dates = deduped
    print(f"  Found {len(events_with_dates)} Teleticket events (Feb–Mar 2026)")
    # Scrape time from each event detail page (skip if SKIP_TELETICKET_FETCH=1 for faster CI runs)
    if not os.environ.get("SKIP_TELETICKET_FETCH"):
        for i, (date_key, ev) in enumerate(events_with_dates):
            if not ev.get("url"):
                continue
            if i > 0:
                time.sleep(0.35)
            t = fetch_event_time(ev["url"])
            if t:
                ev["time"] = t
        with_times = sum(1 for _, ev in events_with_dates if ev.get("time"))
        print(f"  Fetched time for {with_times}/{len(events_with_dates)} Teleticket events")
    else:
        print("  Skipping per-event time fetch (SKIP_TELETICKET_FETCH=1)")

    if not EVENTS_FILE.exists():
        print(f"  {EVENTS_FILE} not found. Run enlima_calendar.py first.")
        return

    with open(EVENTS_FILE, "r", encoding="utf-8") as f:
        events_by_day = json.load(f)

    # Remove existing Teleticket events so we don't duplicate when re-running
    def is_teleticket_event(e):
        u = e.get("url") or ""
        return "teleticket.com.pe" in u and "/Cliente/" not in u and "/Account/" not in u and "/puntosventa" not in u
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
