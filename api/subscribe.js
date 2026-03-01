/**
 * POST /api/subscribe
 * Body: { email: string }
 * Adds the email to Resend contacts (optional segment). Requires RESEND_API_KEY; RESEND_SEGMENT_ID is optional.
 */
const RESEND_API = 'https://api.resend.com';

function jsonResponse(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

export async function POST(request) {
  try {
    const apiKey = process.env.RESEND_API_KEY;
    if (!apiKey) {
      return jsonResponse({ error: 'Servicio de suscripción no configurado.' }, 503);
    }

    const body = await request.json().catch(() => ({}));
    const email = typeof body.email === 'string' ? body.email.trim().toLowerCase() : '';
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!email || !emailRegex.test(email)) {
      return jsonResponse({ error: 'Indica un correo válido.' }, 400);
    }

    const segmentId = process.env.RESEND_SEGMENT_ID || null;
    const payload = {
      email,
      unsubscribed: false,
      ...(segmentId ? { segments: [{ segment_id: segmentId }] } : {}),
    };

    const res = await fetch(`${RESEND_API}/contacts`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${apiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });

    const data = await res.json().catch(() => ({}));

    if (!res.ok) {
      const msg = data.message || data.msg || (data.errors && data.errors[0]?.message) || 'No se pudo suscribir.';
      return jsonResponse({ error: msg }, res.status >= 500 ? 503 : 400);
    }

    return jsonResponse({ ok: true });
  } catch (e) {
    console.error('Subscribe error:', e);
    return jsonResponse({ error: 'Error interno. Intenta más tarde.' }, 500);
  }
}
