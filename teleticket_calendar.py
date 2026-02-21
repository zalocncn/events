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


def fetch_teleticket_page(url=None):
    url = url or TELETICKET_URL
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        return BeautifulSoup(r.text, "lxml")
    except Exception as e:
        print(f"  Error fetching {url}: {e}", file=__import__("sys").stderr)
        return None


def fetch_teleticket():
    """Fetch first page (for backward compatibility)."""
    return fetch_teleticket_page(TELETICKET_URL)


def fetch_all_teleticket_pages(max_pages=20):
    """Fetch /todos and /todos?page=2, ... until a page has no event links."""
    soups = []
    for p in range(1, max_pages + 1):
        url = TELETICKET_URL if p == 1 else f"{TELETICKET_URL}?page={p}"
        soup = fetch_teleticket_page(url)
        if not soup:
            break
        soups.append(soup)
        # Stop if this page has no event links (pagination end)
        links = soup.select('a[href*="teleticket.com.pe"]')
        event_links = [a for a in links if is_event_link(a.get("href") or "")]
        if p > 1 and not event_links:
            break
        if p > 1:
            time.sleep(0.3)
    return soups


def is_event_link(href):
    if not href or href == "#":
        return False
    if any(s in href for s in ("/Cliente/", "/Account/", "/puntosventa", "/Register", "/SignIn", "/SignOut")):
        return False
    return "teleticket.com.pe" in href


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


def date_range_to_keys(first_key, last_key):
    """Return list of YYYY-MM-DD keys from first_key to last_key inclusive."""
    from datetime import datetime, timedelta
    out = []
    try:
        d0 = datetime.strptime(first_key, "%Y-%m-%d")
        d1 = datetime.strptime(last_key, "%Y-%m-%d")
        if d1 < d0:
            d0, d1 = d1, d0
        while d0 <= d1:
            out.append(d0.strftime("%Y-%m-%d"))
            d0 += timedelta(days=1)
    except Exception:
        out = [first_key] if first_key else []
    return out


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


def _make_ev(title, href, first_key, last_key, cat=""):
    """Build event dict and schedule label. Returns (first_key, last_key, ev)."""
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
        "time": "",
        "type": cat or "Teleticket",
        "title": (title or "Evento")[:120],
        "url": href,
        "venue": "",
        "district": "Lima",
        "price": "",
        "source": "Teleticket",
    }
    if schedule:
        ev["schedule"] = schedule
    return (first_key, last_key, ev)


def scrape_teleticket_events(soup):
    """
    Parse all Teleticket events from the page:
    1) Article cards (carousel / featured): h3, p.fecha, p.descripcion, a[href].
    2) "Eventos Por Mes" list: h3 (title) + a[href*="teleticket.com.pe"] with date in link text.
    Returns list of (first_key, last_key, ev) so multi-day events can be expanded to every day.
    """
    seen_urls = set()
    out = []  # (first_key, last_key, ev)
    if not soup:
        return out

    # Skip nav/account links
    def is_event_url(href):
        if not href or href == "#":
            return False
        if any(s in href for s in ("/Cliente/", "/Account/", "/puntosventa",
                                   "/Register", "/SignIn", "/SignOut")):
            return False
        return "teleticket.com.pe" in href

    # ---- 1) Article cards (carousel / listado) ----
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
            if href.startswith("/"):
                href = "https://teleticket.com.pe" + href
            if not is_event_url(href) or href in seen_urls:
                continue
            seen_urls.add(href)

            title_el = card.select_one('h3')
            title = title_el.get_text(strip=True) if title_el else ""
            if not title or len(title) < 3 or title.upper() in ("VER MÁS", "VER TODOS", "VER TODO"):
                continue

            fecha_el = card.select_one('p.fecha')
            date_text = fecha_el.get_text(strip=True) if fecha_el else ""
            first_key, last_key = parse_date_range(date_text)
            if not first_key or not first_key.startswith("2026-"):
                continue

            desc_el = card.select_one('p.descripcion')
            desc = desc_el.get_text(strip=True) if desc_el else ""
            cat = ""
            if "/" in desc:
                cat = desc.split("/")[-1].strip()

            out.append(_make_ev(title, href, first_key, last_key, cat))
        except Exception:
            continue

    # ---- 2) "Eventos Por Mes" section: links with "DD de MES YYYY" in text, title from previous h3 ----
    for a in soup.select('a[href*="teleticket.com.pe"]'):
        try:
            href = (a.get("href") or "").strip()
            if href.startswith("/"):
                href = "https://teleticket.com.pe" + href
            if not is_event_url(href):
                continue
            link_text = a.get_text(separator=" ", strip=True)
            first_key, last_key = parse_date_range(link_text)
            if not first_key or not first_key.startswith("2026-"):
                continue

            title_el = a.find_previous("h3")
            title = title_el.get_text(strip=True) if title_el else ""
            # Skip month headings used as h3 (e.g. "Enero 2026", "Febrero 2026")
            if title and re.match(r"^(Enero|Febrero|Marzo|Abril|Mayo|Junio|Julio|Agosto|Setiembre|Septiembre|Octubre|Noviembre|Diciembre)\s+2026$", title, re.I):
                title = ""
            if not title or len(title) < 3:
                title = re.sub(r"\d{1,2}\s+de\s+\w+\s+\d{4}.*", "", link_text).strip()
                if "/" in title:
                    title = title.split("/")[-1].strip()
                title = title[:80] if title else "Evento Teleticket"
            if title.upper() in ("VER MÁS", "VER TODOS", "VER TODO"):
                continue

            # Category from link text: "VENUE / Category DD de mes YYYY"
            cat = ""
            if "/" in link_text:
                after_slash = link_text.split("/", 1)[-1].strip()
                cat = re.sub(r"\s*\d{1,2}\s+de\s+.*", "", after_slash).strip()

            if href not in seen_urls:
                seen_urls.add(href)
                out.append(_make_ev(title, href, first_key, last_key, cat))
            # If same URL already in out, we could extend date range; for simplicity keep first.
        except Exception:
            continue

    return out


def main():
    print("  Fetching Teleticket (all pages)...")
    soups = fetch_all_teleticket_pages()
    raw_events = []
    for soup in soups:
        raw_events.extend(scrape_teleticket_events(soup))

    # Deduplicate by URL (keep first occurrence)
    seen_url = set()
    unique_raw = []
    for first_key, last_key, ev in raw_events:
        if ev.get("url") in seen_url:
            continue
        seen_url.add(ev["url"])
        unique_raw.append((first_key, last_key, ev))

    # Expand multi-day events to one (date_key, ev) per day in range
    events_with_dates = []  # (date_key, ev)
    for first_key, last_key, ev in unique_raw:
        for d in date_range_to_keys(first_key, last_key):
            events_with_dates.append((d, ev))

    print(f"  Found {len(unique_raw)} Teleticket events → {len(events_with_dates)} day placements (2026)")

    # Fetch time once per unique event (by URL)
    if not os.environ.get("SKIP_TELETICKET_FETCH"):
        urls_done = set()
        fetched = 0
        for i, (_, ev) in enumerate(events_with_dates):
            url = ev.get("url")
            if not url or url in urls_done:
                continue
            urls_done.add(url)
            if fetched > 0:
                time.sleep(0.35)
            t = fetch_event_time(url)
            if t:
                ev["time"] = t
                fetched += 1
            if (fetched) % 15 == 0 and fetched > 0:
                print(f"    Fetched time for {fetched} events...")
        print(f"  Got time for {fetched}/{len(urls_done)} Teleticket events")
    else:
        print("  Skipping per-event time fetch (SKIP_TELETICKET_FETCH=1)")

    if not EVENTS_FILE.exists():
        print(f"  {EVENTS_FILE} not found. Run enlima_calendar.py first.")
        return

    with open(EVENTS_FILE, "r", encoding="utf-8") as f:
        events_by_day = json.load(f)

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
    print(f"  Merged {added} Teleticket dots into calendar. Wrote {EVENTS_FILE}")


if __name__ == "__main__":
    main()
