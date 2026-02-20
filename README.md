# events.com 🗓️

Automated event aggregator for Lima, Peru. Monitors multiple event sources, detects new events, and auto-publishes them to the website.

## Sources
- **Eventbrite** — Free events + all events in Miraflores
- **EnLima.pe** — Lima's event guide
- **Teleticket** — Concerts, shows & ticketed events

## Usage

```bash
# Install dependencies
pip3 install -r requirements.txt

# Full scan: scrape → insert cards → push to GitHub
python3 monitor.py

# Preview only (no changes)
python3 monitor.py --dry-run

# Update HTML but skip git push
python3 monitor.py --no-push
```

## How It Works
1. Scrapes all configured event sources
2. Compares against known events (stored in `events_db.json`)
3. Generates styled card elements matching the site's UI
4. Inserts new cards into `index.html`
5. Commits and pushes to GitHub

## Project Structure
```
events/
├── index.html        # Main website
├── monitor.py        # Scraping & publishing tool
├── events_db.json    # Auto-generated event database
├── requirements.txt  # Python dependencies
└── .gitignore
```
# events
# events
