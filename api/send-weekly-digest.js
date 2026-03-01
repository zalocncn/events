/**
 * GET /api/send-weekly-digest
 * Called by Vercel Cron every Sunday at 12:00 ET (17:00 UTC). Sends weekly event digest to all Resend contacts.
 * Requires: RESEND_API_KEY, CRON_SECRET, SITE_URL (e.g. https://yoursite.vercel.app)
 * Optional: RESEND_SEGMENT_ID to filter contacts; RESEND_FROM_EMAIL for sender.
 */
const RESEND_API = 'https://api.resend.com';

function jsonResponse(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function getWeekDates() {
  const now = new Date();
  const day = now.getDay();
  const start = new Date(now);
  start.setDate(now.getDate() - day);
  const dates = [];
  for (let i = 0; i < 7; i++) {
    const d = new Date(start);
    d.setDate(start.getDate() + i);
    dates.push(formatYMD(d));
  }
  return dates;
}

function formatYMD(d) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

const MONTHS = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'];

function formatDayHeader(dateStr) {
  const [y, m, day] = dateStr.split('-').map(Number);
  const d = new Date(y, m - 1, day);
  const weekdays = ['Dom', 'Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb'];
  const w = weekdays[d.getDay()];
  const monthName = MONTHS[m];
  return `${w} ${day} ${monthName}`;
}

function escapeHtml(s) {
  if (typeof s !== 'string') return '';
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function buildDigestHtml(eventsByDay, siteUrl) {
  const weekDates = getWeekDates();
  let html = `
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;font-family:Inter,sans-serif;background:#1A1A1D;color:#E0E0E0;padding:24px;">
  <div style="max-width:560px;margin:0 auto;">
    <h1 style="color:#fff;font-size:24px;margin-bottom:8px;">Resumen semanal — Eventos en Lima</h1>
    <p style="color:#A0A0A0;font-size:14px;margin-bottom:24px;">Eventos de la semana (Eventis / EnLima, Eventbrite, Teleticket).</p>
`;
  for (const dateStr of weekDates) {
    const events = eventsByDay[dateStr] || [];
    if (events.length === 0) continue;
    html += `
    <div style="margin-bottom:24px;">
      <h2 style="color:#6F42C1;font-size:14px;text-transform:uppercase;letter-spacing:0.02em;margin-bottom:12px;">${escapeHtml(formatDayHeader(dateStr))}</h2>
      <ul style="list-style:none;padding:0;margin:0;">
`;
    for (const ev of events.slice(0, 25)) {
      const title = escapeHtml(ev.title || 'Evento');
      const url = ev.url || siteUrl;
      const meta = [ev.time, ev.venue || ev.district, ev.price].filter(Boolean).join(' · ');
      html += `
        <li style="margin-bottom:12px;padding:12px;background:#242428;border-radius:8px;border:1px solid rgba(255,255,255,0.06);">
          <a href="${escapeHtml(url)}" style="color:#fff;font-weight:600;text-decoration:none;font-size:15px;">${title}</a>
          ${meta ? `<p style="color:#999;font-size:13px;margin:4px 0 0 0;">${escapeHtml(meta)}</p>` : ''}
        </li>`;
    }
    if (events.length > 25) {
      html += `<li style="color:#888;font-size:13px;">y ${events.length - 25} más…</li>`;
    }
    html += `
      </ul>
    </div>`;
  }
  html += `
    <p style="color:#888;font-size:12px;margin-top:24px;padding-top:16px;border-top:1px solid rgba(255,255,255,0.08);">
      <a href="${escapeHtml(siteUrl)}" style="color:#8B5CF6;">Ver calendario completo</a> — Eventis
    </p>
  </div>
</body>
</html>`;
  return html;
}

export async function GET(request) {
  const auth = request.headers.get('authorization') || '';
  const secret = process.env.CRON_SECRET;
  if (secret && auth !== `Bearer ${secret}`) {
    return jsonResponse({ error: 'Unauthorized' }, 401);
  }

  const apiKey = process.env.RESEND_API_KEY;
  const siteUrl = process.env.SITE_URL || (process.env.VERCEL_URL ? `https://${process.env.VERCEL_URL}` : null);
  const fromEmail = process.env.RESEND_FROM_EMAIL || 'onboarding@resend.dev';

  if (!apiKey) {
    return jsonResponse({ error: 'RESEND_API_KEY not set' }, 503);
  }
  if (!siteUrl) {
    return jsonResponse({ error: 'SITE_URL not set' }, 503);
  }

  try {
    const segmentId = process.env.RESEND_SEGMENT_ID || null;
    const listUrl = segmentId
      ? `${RESEND_API}/contacts?segment_id=${encodeURIComponent(segmentId)}`
      : `${RESEND_API}/contacts`;
    const listRes = await fetch(listUrl, {
      headers: { Authorization: `Bearer ${apiKey}` },
    });
    if (!listRes.ok) {
      const err = await listRes.text();
      console.error('Resend list contacts:', err);
      return jsonResponse({ error: 'Failed to list contacts' }, 503);
    }
    const listData = await listRes.json();
    const contacts = listData.data || [];
    const emails = contacts.filter((c) => !c.unsubscribed).map((c) => c.email).filter(Boolean);

    if (emails.length === 0) {
      return jsonResponse({ ok: true, sent: 0, message: 'No subscribers' });
    }

    const eventsUrl = `${siteUrl.replace(/\/$/, '')}/events_by_day.json`;
    const eventsRes = await fetch(eventsUrl);
    if (!eventsRes.ok) {
      return jsonResponse({ error: 'Failed to fetch events' }, 503);
    }
    const eventsByDay = await eventsRes.json();

    const weekDates = getWeekDates();
    const weekEventsByDay = {};
    for (const d of weekDates) {
      weekEventsByDay[d] = eventsByDay[d] || [];
    }
    const html = buildDigestHtml(weekEventsByDay, siteUrl);

    let sent = 0;
    for (const to of emails) {
      const sendRes = await fetch(`${RESEND_API}/emails`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${apiKey}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          from: fromEmail,
          to: [to],
          subject: `Resumen semanal — Eventos en Lima (${formatDayHeader(weekDates[0])} – ${formatDayHeader(weekDates[6])})`,
          html,
        }),
      });
      if (sendRes.ok) sent++;
      else console.error('Resend send failed for', to, await sendRes.text());
    }

    return jsonResponse({ ok: true, sent, total: emails.length });
  } catch (e) {
    console.error('send-weekly-digest error:', e);
    return jsonResponse({ error: String(e.message || e) }, 500);
  }
}
