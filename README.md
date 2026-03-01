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

## Weekly email digest

Users can sign up in the footer to receive a **weekly roster of events** (every **Sunday at 12:00 noon ET**). The digest is sent via [Resend](https://resend.com).

### Setup (Vercel)

1. **Resend** — Create an account at resend.com, get an API key. Optionally create an Audience and Segment so only digest subscribers are listed.
2. **Environment variables** (Vercel → Settings → Environment Variables):
   - `RESEND_API_KEY` (required)
   - `SITE_URL` (required, e.g. `https://yoursite.vercel.app`)
   - `CRON_SECRET` (recommended; Vercel sends it when triggering the cron)
   - `RESEND_SEGMENT_ID` (optional; segment ID so only digest subscribers get the email)
   - `RESEND_FROM_EMAIL` (optional; default `onboarding@resend.dev`)
3. **Cron** — In `vercel.json` the job runs every Sunday at 17:00 UTC (noon ET). For noon EDT use schedule `0 16 * * 0`.
