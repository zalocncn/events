#!/usr/bin/env python3
"""
events.com — Event Monitor & Auto-Publisher
============================================
Scrapes events from configured sources, compares against existing entries
in the HTML, inserts new event cards matching the Tailwind UI, and pushes to GitHub.

Sources:
  - Eventbrite (Miraflores free + all events)
  - EnLima.pe
  - Teleticket.com.pe

Usage:
  python3 monitor.py              # Run full scan + publish
  python3 monitor.py --dry-run    # Preview without modifying files
  python3 monitor.py --no-push    # Update HTML but skip git push
"""

import os
import re
import sys
import json
import hashlib
import subprocess
import argparse
import time
from datetime import datetime
from pathlib import Path
from html import escape

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Installing required packages...")
    subprocess.check_call([sys.executable, "-m", "pip", "install",
                           "requests", "beautifulsoup4", "lxml"])
    import requests
    from bs4 import BeautifulSoup

# ─── CONFIGURATION ──────────────────────────────────────────────────────────

PROJECT_DIR = Path(__file__).parent
HTML_FILE = PROJECT_DIR / "index.html"
EVENTS_DB = PROJECT_DIR / "events_db.json"
GIT_REMOTE = "origin"
GIT_BRANCH = "main"
EVENTS_GRID_START = "<!-- EVENTS_GRID_START -->"
EVENTS_GRID_END = "<!-- EVENTS_GRID_END -->"

SOURCES = [
    {
        "name": "Eventbrite Free",
        "key": "eventbrite",
        "url": "https://www.eventbrite.com.pe/d/peru--miraflores/free--events/",
        "scraper": "scrape_eventbrite",
    },
    {
        "name": "Eventbrite All",
        "key": "eventbrite",
        "url": "https://www.eventbrite.com.pe/d/peru--miraflores/events/",
        "scraper": "scrape_eventbrite",
    },
    {
        "name": "EnLima",
        "key": "enlima",
        "url": "https://enlima.pe/",
        "scraper": "scrape_enlima",
    },
    {
        "name": "Teleticket",
        "key": "teleticket",
        "url": "https://teleticket.com.pe/todos",
        "scraper": "scrape_teleticket",
    },
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

CATEGORY_KEYWORDS = {
    "Music": ["concert", "concierto", "music", "música", "live", "band", "dj",
              "festival", "rock", "jazz", "salsa", "cumbia", "reggaeton", "opera",
              "sinfónica", "orquesta", "recital", "show musical"],
    "Sports": ["sport", "deporte", "fútbol", "football", "basketball", "baseball",
               "volleyball", "marathon", "maratón", "run", "carrera", "yoga",
               "fitness", "gym", "torneo", "campeonato"],
    "Arts & Culture": ["art", "arte", "museum", "museo", "gallery", "galería",
                       "exhibition", "exposición", "theater", "teatro", "dance",
                       "danza", "ballet", "pintura", "escultura", "cultura",
                       "cine", "film", "película", "literatura", "libro"],
}

SOURCE_DOT_COLORS = {
    "eventbrite": "#FFC107",
    "enlima": "#5CB85C",
    "teleticket": "#3B82F6",
}

SOURCE_LABELS = {
    "eventbrite": "Eventbrite",
    "enlima": "EnLima",
    "teleticket": "Teleticket",
}

FALLBACK_IMAGES = {
    "Music": "https://images.unsplash.com/photo-1598387181032-a3103a2db5b3?q=80&w=600&auto=format&fit=crop",
    "Sports": "https://images.unsplash.com/photo-1504450758481-7338eba7524a?q=80&w=600&auto=format&fit=crop",
    "Arts & Culture": "https://images.unsplash.com/photo-1465847899084-d164df4dedc6?q=80&w=600&auto=format&fit=crop",
    "Miscellaneous": "https://images.unsplash.com/photo-1492684223066-81342ee5ff30?q=80&w=600&auto=format&fit=crop",
}


class C:
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    CYAN = "\033[96m"
    DIM = "\033[2m"
    BOLD = "\033[1m"
    END = "\033[0m"


# ─── EVENT MODEL ─────────────────────────────────────────────────────────────

def make_event_id(title, source):
    raw = f"{source}:{title.strip().lower()}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def classify_category(title, description=""):
    text = f"{title} {description}".lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return category
    return "Miscellaneous"


def make_event(title, url, source_key, date="", location="", description="",
               image_url="", is_free=False, price="", category=""):
    if not category:
        category = classify_category(title, description)
    return {
        "id": make_event_id(title, source_key),
        "title": title.strip(),
        "url": url.strip(),
        "source": source_key,
        "date": date.strip(),
        "location": location.strip(),
        "description": description.strip()[:200],
        "image_url": image_url.strip(),
        "is_free": is_free,
        "price": price.strip(),
        "category": category,
        "scraped_at": datetime.now().isoformat(),
    }


# ─── SCRAPERS ────────────────────────────────────────────────────────────────

def fetch_page(url, timeout=15):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "lxml")
    except Exception as e:
        print(f"  {C.RED}✗ Error fetching {url}: {e}{C.END}")
        return None


def is_event_detail_url(url, source_key):
    """True only if URL points to a specific event page, not a listing or homepage."""
    if not url or url.strip() in ("", "#"):
        return False
    url = url.split("?")[0].rstrip("/")
    if source_key == "eventbrite":
        return "/e/" in url
    if source_key == "enlima":
        # Must have path beyond domain (e.g. /eventos/foo or /post/bar)
        if "enlima.pe" not in url:
            return True
        path = url.replace("https://enlima.pe", "").replace("http://enlima.pe", "")
        return len(path) > 1 and path != "/"
    if source_key == "teleticket":
        if "teleticket.com.pe" not in url:
            return True
        path = url.replace("https://teleticket.com.pe", "").replace("http://teleticket.com.pe", "")
        return len(path) > 1 and path != "/"
    return True


def scrape_eventbrite(source):
    soup = fetch_page(source["url"])
    if not soup:
        return []
    events = []
    is_free_page = "free" in source["url"]
    cards = soup.select('[data-testid="event-card"]')
    if not cards:
        cards = soup.select('.search-event-card-wrapper')
    if not cards:
        cards = soup.select('.eds-event-card-content__content')
    if not cards:
        cards = soup.select('a[href*="/e/"]')
    for card in cards[:25]:
        try:
            link = card if card.name == 'a' else card.find('a', href=True)
            if not link or '/e/' not in link.get('href', ''):
                continue
            url = link['href']
            if not url.startswith('http'):
                url = 'https://www.eventbrite.com.pe' + url
            if not is_event_detail_url(url, "eventbrite"):
                continue
            title_el = card.select_one('h2, h3, [data-testid="event-card-title"], .eds-text-bs')
            title = title_el.get_text(strip=True) if title_el else link.get_text(strip=True)
            if not title or len(title) < 5:
                continue
            date_el = card.select_one('[data-testid="event-card-date"], .eds-event-card-content__sub-title, time')
            date = date_el.get_text(strip=True) if date_el else ""
            loc_el = card.select_one('[data-testid="event-card-location"], .card-text--truncated__one')
            location = loc_el.get_text(strip=True) if loc_el else "Miraflores, Lima"
            img_el = card.select_one('img[src*="img.evbuc"], img[data-src], img')
            image = ""
            if img_el:
                image = img_el.get('src') or img_el.get('data-src', '')
            events.append(make_event(
                title=title, url=url, source_key="eventbrite",
                date=date, location=location, image_url=image,
                is_free=is_free_page
            ))
        except Exception:
            continue
    return events


def scrape_enlima(source):
    soup = fetch_page(source["url"])
    if not soup:
        return []
    events = []
    cards = soup.select('article, .event-card, .card, .entry, .post-item, .evento')
    if not cards:
        cards = soup.select('[class*="event"], [class*="card"], [class*="item"]')
    for card in cards[:25]:
        try:
            link = card.find('a', href=True)
            if not link:
                continue
            url = link['href']
            if not url.startswith('http'):
                url = 'https://enlima.pe' + url
            if url.rstrip('/') == 'https://enlima.pe' or url == '#':
                continue
            if not is_event_detail_url(url, "enlima"):
                continue
            title_el = card.select_one('h2, h3, h4, .title, .entry-title')
            title = title_el.get_text(strip=True) if title_el else link.get_text(strip=True)
            if not title or len(title) < 5:
                continue
            desc_el = card.select_one('p, .excerpt, .description, .entry-summary')
            desc = desc_el.get_text(strip=True) if desc_el else ""
            date_el = card.select_one('time, .date, .fecha, [class*="date"]')
            date = date_el.get_text(strip=True) if date_el else ""
            img_el = card.select_one('img')
            image = ""
            if img_el:
                image = img_el.get('src') or img_el.get('data-src', '')
                if image and not image.startswith('http'):
                    image = 'https://enlima.pe' + image
            events.append(make_event(
                title=title, url=url, source_key="enlima",
                date=date, description=desc, image_url=image,
                location="Lima"
            ))
        except Exception:
            continue
    return events


def scrape_teleticket(source):
    soup = fetch_page(source["url"])
    if not soup:
        return []
    events = []
    cards = soup.select('.event-card, .card, article, .show-card, [class*="event"]')
    if not cards:
        cards = soup.select('a[href*="/evento/"], a[href*="/show/"]')
    for card in cards[:25]:
        try:
            link = card if card.name == 'a' else card.find('a', href=True)
            if not link:
                continue
            url = link['href']
            if not url.startswith('http'):
                url = 'https://teleticket.com.pe' + url
            if url.rstrip('/') == 'https://teleticket.com.pe':
                continue
            if not is_event_detail_url(url, "teleticket"):
                continue
            title_el = card.select_one('h2, h3, h4, .title, .name, .card-title')
            title = title_el.get_text(strip=True) if title_el else link.get_text(strip=True)
            if not title or len(title) < 5:
                continue
            date_el = card.select_one('.date, .fecha, time, [class*="date"]')
            date = date_el.get_text(strip=True) if date_el else ""
            loc_el = card.select_one('.venue, .location, .lugar, [class*="location"]')
            location = loc_el.get_text(strip=True) if loc_el else "Lima"
            price_el = card.select_one('.price, .precio, [class*="price"]')
            price = price_el.get_text(strip=True) if price_el else ""
            img_el = card.select_one('img')
            image = ""
            if img_el:
                image = img_el.get('src') or img_el.get('data-src', '')
                if image and not image.startswith('http'):
                    image = 'https://teleticket.com.pe' + image
            events.append(make_event(
                title=title, url=url, source_key="teleticket",
                date=date, location=location, image_url=image,
                price=price
            ))
        except Exception:
            continue
    return events


SCRAPER_MAP = {
    "scrape_eventbrite": scrape_eventbrite,
    "scrape_enlima": scrape_enlima,
    "scrape_teleticket": scrape_teleticket,
}


# ─── ENRICH FROM EVENT PAGE (fetch actual article for date + description) ────

def enrich_event(event, db):
    """Fetch the event's detail page and extract date + description. Use db cache if already enriched.
    Returns True if we did an HTTP fetch, False if we used cache."""
    eid = event["id"]
    if eid in db.get("events", {}):
        stored = db["events"][eid]
        if stored.get("enriched") or stored.get("description"):
            event["description"] = stored.get("description", event.get("description", ""))
            if stored.get("date"):
                event["date"] = stored["date"]
            if stored.get("image_url"):
                event["image_url"] = stored["image_url"]
            event["enriched"] = True
            return False
    try:
        soup = fetch_page(event["url"], timeout=10)
        if not soup:
            return False
        # Description: og:description or meta description
        desc = ""
        og_desc = soup.select_one('meta[property="og:description"]')
        if og_desc and og_desc.get("content"):
            desc = og_desc["content"].strip()
        if not desc:
            meta_desc = soup.select_one('meta[name="description"]')
            if meta_desc and meta_desc.get("content"):
                desc = meta_desc["content"].strip()
        if desc:
            event["description"] = desc[:300]
        # Date: time[datetime], itemprop startDate, or event meta
        date_val = ""
        time_el = soup.select_one('time[datetime]')
        if time_el and time_el.get("datetime"):
            date_val = time_el["datetime"]
            # Prefer human-readable from same element
            if time_el.get_text(strip=True):
                date_val = time_el.get_text(strip=True)
        if not date_val:
            start_el = soup.select_one('[itemprop="startDate"]')
            if start_el:
                date_val = start_el.get("datetime") or start_el.get_text(strip=True)
        if not date_val:
            start_meta = soup.select_one('meta[property="event:start_date"]')
            if start_meta and start_meta.get("content"):
                date_val = start_meta["content"]
        if date_val:
            event["date"] = date_val.strip()
        # Image: og:image
        og_img = soup.select_one('meta[property="og:image"]')
        if og_img and og_img.get("content"):
            event["image_url"] = og_img["content"].strip()
        event["enriched"] = True
        return True
    except Exception:
        pass
    return False


# ─── DATABASE ────────────────────────────────────────────────────────────────

def load_db():
    if EVENTS_DB.exists():
        with open(EVENTS_DB, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"events": {}, "last_scan": None}


def save_db(db):
    db["last_scan"] = datetime.now().isoformat()
    with open(EVENTS_DB, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)


# ─── TAILWIND CARD GENERATION (matches existing UI exactly) ─────────────────

def generate_card_html(event):
    title_safe = escape(event["title"])
    category = event.get("category", "Miscellaneous")
    category_upper = escape(category.upper())
    location_safe = escape(event.get("location", "Lima"))
    source_label = SOURCE_LABELS.get(event["source"], event["source"].title())
    dot_color = SOURCE_DOT_COLORS.get(event["source"], "#6F42C1")

    img_url = event.get("image_url", "")
    if not img_url:
        img_url = FALLBACK_IMAGES.get(category, FALLBACK_IMAGES["Miscellaneous"])

    date_text = event.get("date", "")
    if not date_text:
        date_text = datetime.now().strftime("%b %d")

    event_url = escape(event["url"])

    description_html = ""
    desc = (event.get("description") or "").strip()
    if desc:
        desc_safe = escape(desc[:160] + ("…" if len(desc) > 160 else ""))
        description_html = f'<p class="text-sm text-[#A0A0A0] line-clamp-2 leading-snug">{desc_safe}</p>'

    badge_html = ""
    if event.get("is_free"):
        badge_html = (
            '\n                    <div class="absolute top-3 left-3 bg-[#5CB85C]/90 '
            'backdrop-blur-sm border border-[rgba(255,255,255,0.1)] px-2 py-0.5 '
            'rounded-[4px] text-[10px] font-semibold text-white uppercase '
            'tracking-wider">Gratis</div>'
        )
    elif event.get("price"):
        price_safe = escape(event["price"])
        badge_html = (
            f'\n                    <div class="absolute top-3 left-3 bg-[#1A1A1D]/90 '
            f'backdrop-blur-sm border border-[rgba(255,255,255,0.1)] px-2 py-0.5 '
            f'rounded-[4px] text-[10px] font-semibold text-white uppercase '
            f'tracking-wider">{price_safe}</div>'
        )

    card = f"""
            <!-- EVENT:{event["id"]} | src:{event["source"]} -->
            <a href="{event_url}" target="_blank" rel="noopener noreferrer"
               data-event-id="{event["id"]}" data-source="{event["source"]}"
               class="flex flex-col bg-[#242428] rounded-[10px] border border-[rgba(255,255,255,0.05)] shadow-[0_6px_20px_rgba(0,0,0,0.28)] overflow-hidden group hover:-translate-y-[3px] hover:shadow-[0_12px_40px_rgba(0,0,0,0.35)] transition-all duration-200 ease-out no-underline">
                <div class="relative h-44 bg-[#2A2A2E] overflow-hidden">
                    <img src="{img_url}" alt="{title_safe}" loading="lazy"
                         class="w-full h-full object-cover opacity-85 group-hover:opacity-100 group-hover:scale-[1.02] transition-all duration-500"
                         onerror="this.style.display='none'">
                    <button class="absolute top-3 right-3 w-7 h-7 bg-[#1A1A1D]/80 backdrop-blur-sm rounded-full flex items-center justify-center text-[#E0E0E0] hover:text-white hover:bg-[#6F42C1] transition-colors border border-[rgba(255,255,255,0.1)]">
                        <i data-lucide="info" class="w-3.5 h-3.5" stroke-width="1.5"></i>
                    </button>{badge_html}
                    <div class="absolute bottom-3 left-3 bg-[#1A1A1D]/90 backdrop-blur-md border border-[rgba(255,255,255,0.1)] px-2.5 py-1 rounded-[6px] text-xs font-medium text-white shadow-sm flex items-center gap-1.5">
                        <div class="w-1.5 h-1.5 rounded-full" style="background:{dot_color}"></div>
                        {escape(date_text)}
                    </div>
                </div>
                <div class="flex flex-col flex-1 p-5 gap-2.5">
                    <div class="flex items-center justify-between">
                        <span class="text-xs font-medium tracking-wide text-[#999999] uppercase">{category_upper}</span>
                        <span class="text-[10px] font-medium tracking-wide text-[#666666] uppercase">{escape(source_label)}</span>
                    </div>
                    <h3 class="text-base font-semibold leading-snug text-white group-hover:text-[#8B5CF6] transition-colors line-clamp-2">
                        {title_safe}
                    </h3>
                    {description_html}
                    <div class="flex items-start gap-2 text-sm text-[#C0C0C0] mt-auto pt-2">
                        <i data-lucide="map-pin" class="w-4 h-4 shrink-0 mt-0.5 text-[#6F42C1]"></i>
                        <span class="line-clamp-2 leading-relaxed">{location_safe}</span>
                    </div>
                </div>
                <div class="px-5 pb-5">
                    <div class="w-full flex items-center justify-center gap-2 h-9 rounded-[6px] text-sm font-medium text-[#E0E0E0] bg-[#2E2E32] group-hover:bg-[#35353A] border border-[rgba(255,255,255,0.04)] transition-colors group-hover:border-[rgba(111,66,193,0.35)]">
                        <i data-lucide="external-link" class="w-4 h-4 text-[#A0A0A0] group-hover:text-[#8B5CF6] transition-colors" stroke-width="1.5"></i>
                        View Event
                    </div>
                </div>
            </a>
            <!-- /EVENT:{event["id"]} -->"""

    return card


# ─── HTML FILE MANIPULATION ─────────────────────────────────────────────────

def get_existing_event_ids(html_content):
    return set(re.findall(r'data-event-id="([^"]+)"', html_content))


def replace_events_grid(all_events):
    """Replace the entire events grid in index.html with cards for all_events."""
    if not HTML_FILE.exists():
        print(f"  {C.RED}✗ HTML file not found: {HTML_FILE}{C.END}")
        return False
    html = HTML_FILE.read_text(encoding="utf-8")
    if EVENTS_GRID_START not in html or EVENTS_GRID_END not in html:
        print(f"  {C.RED}✗ Could not find {EVENTS_GRID_START} / {EVENTS_GRID_END} in HTML{C.END}")
        return False
    cards_html = "\n".join(generate_card_html(e) for e in all_events)
    pattern = re.compile(
        re.escape(EVENTS_GRID_START) + r".*?" + re.escape(EVENTS_GRID_END),
        re.DOTALL
    )
    new_grid = f"{EVENTS_GRID_START}\n{cards_html}\n            {EVENTS_GRID_END}"
    new_html = pattern.sub(new_grid, html, count=1)
    if new_html == html:
        return False
    total_events = len(all_events)
    new_html = re.sub(r'(\d+)\s+items?\s+more', f'{total_events} items more', new_html)
    HTML_FILE.write_text(new_html, encoding="utf-8")
    print(f"  {C.GREEN}✓ Replaced events grid with {len(all_events)} card(s){C.END}")
    return True


# ─── GIT OPERATIONS ─────────────────────────────────────────────────────────

def git_push():
    try:
        os.chdir(PROJECT_DIR)
        result = subprocess.run(["git", "status"], capture_output=True, text=True, cwd=PROJECT_DIR)
        if result.returncode != 0:
            print(f"  {C.YELLOW}⚠ Not a git repo. Initializing...{C.END}")
            subprocess.run(["git", "init"], cwd=PROJECT_DIR, check=True)
            subprocess.run(["git", "branch", "-M", GIT_BRANCH], cwd=PROJECT_DIR, check=True)
            print(f"  {C.YELLOW}⚠ Set up remote: git remote add origin <url>{C.END}")
            return False

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        subprocess.run(["git", "add", "."], cwd=PROJECT_DIR, check=True)

        status = subprocess.run(["git", "diff", "--cached", "--quiet"],
                                cwd=PROJECT_DIR, capture_output=True)
        if status.returncode == 0:
            print(f"  {C.DIM}No changes to commit{C.END}")
            return True

        commit_msg = f"🗓️ Auto-update events — {timestamp}"
        subprocess.run(["git", "commit", "-m", commit_msg], cwd=PROJECT_DIR, check=True)
        print(f"  {C.GREEN}✓ Committed: {commit_msg}{C.END}")

        push_result = subprocess.run(
            ["git", "push", GIT_REMOTE, GIT_BRANCH],
            cwd=PROJECT_DIR, capture_output=True, text=True
        )
        if push_result.returncode == 0:
            print(f"  {C.GREEN}✓ Pushed to {GIT_REMOTE}/{GIT_BRANCH}{C.END}")
            return True
        else:
            print(f"  {C.YELLOW}⚠ Push failed: {push_result.stderr.strip()}{C.END}")
            return False

    except FileNotFoundError:
        print(f"  {C.RED}✗ Git not found{C.END}")
        return False
    except Exception as e:
        print(f"  {C.RED}✗ Git error: {e}{C.END}")
        return False


# ─── MAIN ────────────────────────────────────────────────────────────────────

def run_monitor(dry_run=False, no_push=False):
    print(f"\n{C.BOLD}{'═' * 60}{C.END}")
    print(f"{C.BOLD}  🔍  events.com — Event Monitor & Auto-Publisher{C.END}")
    print(f"{C.BOLD}{'═' * 60}{C.END}")
    print(f"  {C.DIM}{datetime.now().strftime('%A %d %B %Y, %H:%M:%S')}{C.END}\n")

    if dry_run:
        print(f"  {C.YELLOW}⚡ DRY RUN — no files will be modified{C.END}\n")

    db = load_db()
    all_events = []
    seen_ids = set()

    for source in SOURCES:
        print(f"  {C.CYAN}▸ Scanning: {source['name']}{C.END}")
        print(f"    {C.DIM}{source['url']}{C.END}")

        scraper_fn = SCRAPER_MAP.get(source["scraper"])
        if not scraper_fn:
            print(f"    {C.RED}✗ Unknown scraper: {source['scraper']}{C.END}")
            continue

        events = scraper_fn(source)
        print(f"    Found {len(events)} event(s)")

        for e in events:
            db["events"][e["id"]] = e
            if e["id"] not in seen_ids:
                seen_ids.add(e["id"])
                all_events.append(e)
        print()

    all_events.sort(key=lambda e: (e.get("date") or "", e["title"]))

    print(f"{'─' * 60}")
    print(f"  {C.BOLD}Total: {len(all_events)} events from all sources{C.END}")

    if dry_run:
        print(f"\n  {C.YELLOW}Dry run complete — no files modified.{C.END}\n")
        return

    print(f"\n  {C.CYAN}▸ Enriching events from detail pages (date + description)...{C.END}")
    for i, e in enumerate(all_events):
        did_fetch = enrich_event(e, db)
        db["events"][e["id"]] = e
        if did_fetch:
            time.sleep(0.4)
        if (i + 1) % 10 == 0:
            print(f"    {C.DIM}Processed {i + 1}/{len(all_events)}{C.END}")
    save_db(db)

    print(f"\n  {C.CYAN}▸ Updating homepage with full event list...{C.END}")
    changed = replace_events_grid(all_events)

    if changed and not no_push:
        print(f"\n  {C.CYAN}▸ Pushing to GitHub...{C.END}")
        git_push()
    elif no_push and changed:
        print(f"\n  {C.YELLOW}⚠ Skipping git push (--no-push){C.END}")

    print(f"\n{C.GREEN}  ✓ Done!{C.END}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="events.com — Monitor event sources and auto-publish"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview without modifying files")
    parser.add_argument("--no-push", action="store_true",
                        help="Update HTML but skip git push")
    args = parser.parse_args()
    run_monitor(dry_run=args.dry_run, no_push=args.no_push)
